"""FastAPI ingress. POST /api/v1/agent/query. Tenant binding: X-Tenant-ID header must equal body.tenant_id."""
from __future__ import annotations
import time
import collections
import os
import jwt
from fastapi import FastAPI, Header, HTTPException, Request, Response as HttpResponse
from .tracing import Tracer
from pydantic import BaseModel, ConfigDict, Field
from .tenancy import validate_tenant_id


class QueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str
    user_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=128)


class TokenBucket:
    """Per-tenant rate limit (noisy-neighbour control, X-07). rate tokens/s, burst capacity."""
    def __init__(self, rate: float, burst: int, clock=time.monotonic):
        self.rate, self.burst, self.clock = rate, burst, clock
        self.state: dict[str, tuple[float, float]] = {}

    def allow(self, tenant: str) -> bool:
        now = self.clock(); tokens, last = self.state.get(tenant, (self.burst, now))
        tokens = min(self.burst, tokens + (now - last) * self.rate)
        if tokens < 1: self.state[tenant] = (tokens, now); return False
        self.state[tenant] = (tokens - 1, now); return True


def tenant_from_token(authorization: str | None, secret: str) -> str:
    if not authorization or not authorization.lower().startswith("bearer "): raise HTTPException(401, "missing bearer token")
    try: claims = jwt.decode(authorization[7:], secret, algorithms=["HS256"], options={"require": ["exp", "tenant_id"]})
    except jwt.PyJWTError: raise HTTPException(401, "invalid token")
    return claims["tenant_id"]


def create_app(orchestrator, jwt_secret: str | None = None, rate_per_s: float = 0, burst: int = 0, tracer: Tracer | None = None) -> FastAPI:
    app = FastAPI(title="Unreliable Assistant", version="0.1")
    app.state.orch = orchestrator
    app.state.started = time.time()
    app.state.counters = {"requests": 0, "errors_5xx": 0, "rate_limited": 0}
    app.state.tracer = tracer or Tracer()
    bucket = TokenBucket(rate_per_s, burst) if rate_per_s > 0 else None

    @app.get("/health")
    async def health():
        return {"status": "ok", "uptime_s": round(time.time() - app.state.started, 1)}

    @app.post("/api/v1/agent/query")
    async def query(body: QueryIn, response: HttpResponse, x_tenant_id: str | None = Header(default=None),
                    authorization: str | None = Header(default=None), traceparent: str | None = Header(default=None)):
        try:
            validate_tenant_id(body.tenant_id)
        except ValueError:
            raise HTTPException(422, "invalid tenant_id")
        if jwt_secret:                                            # token tenant is authoritative when auth is enabled
            if tenant_from_token(authorization, jwt_secret) != body.tenant_id: raise HTTPException(403, "tenant mismatch")
        if x_tenant_id is None or x_tenant_id != body.tenant_id:
            raise HTTPException(403, "tenant mismatch")           # header is authoritative; body cannot switch tenants
        if bucket and not bucket.allow(body.tenant_id):
            app.state.counters["rate_limited"] += 1; raise HTTPException(429, "rate limit exceeded")
        app.state.counters["requests"] += 1
        with app.state.tracer.span("http.query", traceparent, tenant=body.tenant_id) as sp:
            response.headers["traceparent"] = Tracer.header(sp)
            try:
                r = await app.state.orch.handle(body.tenant_id, body.user_id, body.query, body.session_id)
            except Exception:                                      # noqa: BLE001  never leak internals
                app.state.counters["errors_5xx"] += 1
                raise HTTPException(500, "internal error")
        return {"tenant_id": body.tenant_id, "answer": r.text, "route": r.route, "abstained": r.abstained, "blocked": r.blocked,
                "pending_approval": r.pending_approval, "mode": r.mode, "citations": r.citations, "request_id": r.request_id,
                "spans_ms": {k: round(v, 2) for k, v in r.spans_ms.items()}}

    return app
