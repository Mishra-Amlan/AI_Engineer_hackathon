"""FastAPI ingress. POST /api/v1/agent/query. Tenant binding: X-Tenant-ID header must equal body.tenant_id."""
from __future__ import annotations
import time
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .tenancy import validate_tenant_id


class QueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str
    user_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=128)


def create_app(orchestrator) -> FastAPI:
    app = FastAPI(title="Unreliable Assistant", version="0.1")
    app.state.orch = orchestrator
    app.state.started = time.time()
    app.state.counters = {"requests": 0, "errors_5xx": 0}

    @app.get("/health")
    async def health():
        return {"status": "ok", "uptime_s": round(time.time() - app.state.started, 1)}

    @app.post("/api/v1/agent/query")
    async def query(body: QueryIn, x_tenant_id: str | None = Header(default=None)):
        try:
            validate_tenant_id(body.tenant_id)
        except ValueError:
            raise HTTPException(422, "invalid tenant_id")
        if x_tenant_id is None or x_tenant_id != body.tenant_id:
            raise HTTPException(403, "tenant mismatch")           # header is authoritative; body cannot switch tenants
        app.state.counters["requests"] += 1
        try:
            r = await app.state.orch.handle(body.tenant_id, body.user_id, body.query, body.session_id)
        except Exception:                                          # noqa: BLE001  never leak internals
            app.state.counters["errors_5xx"] += 1
            raise HTTPException(500, "internal error")
        return {"tenant_id": body.tenant_id, "answer": r.text, "route": r.route, "abstained": r.abstained, "blocked": r.blocked,
                "pending_approval": r.pending_approval, "mode": r.mode, "citations": r.citations, "request_id": r.request_id,
                "spans_ms": {k: round(v, 2) for k, v in r.spans_ms.items()}}

    return app
