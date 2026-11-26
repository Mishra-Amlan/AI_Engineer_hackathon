"""Production-shaped entrypoint wiring the REAL pipeline:  uvicorn assistant.main:app
PII/injection hooks -> semantic cache -> local+LLM triage -> retrieval(hybrid, int8 ONNX) -> generation + verification -> HITL.
State-store here is an in-memory DEMO (SKU/LOT table); swap `build_state_tools` for Postgres in production."""
from __future__ import annotations
import asyncio
import json
import os
from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .agent.generation import GenerationPipeline
from .agent.harness import Tier, ToolHarness, ToolSpec
from .agent.hitl import HitlError, HitlQueue
from .agents.local_triage import LocalTriage
from .agent.subagents import ExecutionSubagent, RetrievalSubagent, retrieval_tool
from .agents.triage import TriageAgent
from .api import create_app, tenant_from_token
from .audit import AuditLog
from .cache import SemanticCache
from .config import Settings
from .orchestrator import Orchestrator
from .plugins.base import PluginManager
from .plugins.injection import InjectionShield
from .plugins.pii import PiiRedactor
from .rag.ingest import Chunk
from .rag.onnx_models import OnnxEmbedder, OnnxReranker
from .rag.retriever import HybridRetriever
from .router.providers import OpenRouterProvider
from .router.router import ModelRouter

DEMO_SKUS = {f"SKU-{i:03d}": {"sku": f"SKU-{i:03d}", "status": "ACTIVE", "qty": 40 + i} for i in range(1, 200)}
DEMO_LOTS = {f"LOT-{i:05d}": {"lot": f"LOT-{i:05d}", "status": "QUARANTINED" if i % 7 == 0 else "RELEASED"} for i in range(1, 500)}


class SkuIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(pattern=r"^SKU-\d{3}$")

class LotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot: str = Field(pattern=r"^LOT-\d{5}$")

class TransIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str = Field(pattern=r"^(SKU-\d{3}|LOT-\d{5})$")
    to_state: str = Field(pattern=r"^[A-Z_]{3,20}$")


def build_state_tools():
    async def sku(a: SkuIn): return DEMO_SKUS.get(a.sku, {"error": "not found"})
    async def lot(a: LotIn): return DEMO_LOTS.get(a.lot, {"error": "not found"})
    async def trans(a: TransIn):
        (DEMO_LOTS if a.entity_id.startswith("LOT") else DEMO_SKUS).get(a.entity_id, {})["status"] = a.to_state
        return {"applied": True, "entity": a.entity_id, "state": a.to_state}
    return [ToolSpec("lookup_sku", Tier.TIER_1_READ, SkuIn, sku), ToolSpec("lookup_lot", Tier.TIER_1_READ, LotIn, lot),
            ToolSpec("transition_workflow", Tier.TIER_3_MUTATE, TransIn, trans)], trans


def build() -> tuple:
    s = Settings.load(".env")
    router = ModelRouter(s, OpenRouterProvider(s.openrouter_api_key.get_secret_value(), s.openrouter_base_url))
    emb = OnnxEmbedder()
    chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
    tenants = {t.strip() for t in os.getenv("DEMO_TENANTS", "demo").split(",")}
    retrievers = {t: HybridRetriever([Chunk(**{**c.__dict__, "tenant_id": t}) for c in chunks], emb, OnnxReranker(max_len=256)) for t in tenants}

    class PerTenant:                                  # per-tenant index (isolation by construction)
        def retrieve(self, tenant, q):
            if tenant not in retrievers: raise PermissionError("unknown tenant")
            return retrievers[tenant].retrieve(tenant, q)
    audit = AuditLog(s.audit_hash_seed.get_secret_value())
    tools, trans = build_state_tools()
    hitl = HitlQueue(audit, {"transition_workflow": lambda args: trans(TransIn(**args))})
    state_h = ToolHarness(tools, hitl_enqueue=hitl.submit, step_timeout_s=5)
    rag_h = ToolHarness([retrieval_tool(PerTenant(), lambda: _current_tenant.get(), timeout_s=20)])
    orch = Orchestrator(PluginManager([PiiRedactor(), InjectionShield()]), TriageAgent(router, local=LocalTriage(emb)), RetrievalSubagent(rag_h),
                        GenerationPipeline(router, s.model_verifier), ExecutionSubagent(state_h, router, total_budget_ms=20000), audit,
                        cache=SemanticCache(emb, threshold=0.92, ttl=s.cache_ttl_seconds, jitter=s.cache_ttl_jitter_seconds))
    return orch, hitl, audit, s


import contextvars
_current_tenant: contextvars.ContextVar[str] = contextvars.ContextVar("tenant", default="demo")


class TenantBoundOrchestrator:
    """Sets the tenant for the retrieval tool via a contextvar (the tool handler runs in a worker thread: copy_context)."""
    def __init__(self, inner: Orchestrator): self.inner = inner
    async def handle(self, tenant_id, user_id, text, session="s"):
        _current_tenant.set(tenant_id); return await self.inner.handle(tenant_id, user_id, text, session)


orch, hitl, audit, settings = build()
JWT_SECRET = os.getenv("API_JWT_SECRET") or None
app = create_app(TenantBoundOrchestrator(orch), jwt_secret=JWT_SECRET, rate_per_s=float(os.getenv("RATE_PER_TENANT_S", "5")), burst=int(os.getenv("RATE_BURST", "20")))


def _approver(authorization: str | None, tenant_id: str) -> str:
    if not JWT_SECRET: raise HTTPException(403, "approval API requires API_JWT_SECRET (no unauthenticated approvals)")
    import jwt
    try: c = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "tenant_id", "sub"]})
    except Exception: raise HTTPException(401, "invalid token")
    if c["tenant_id"] != tenant_id or "approver" not in c.get("roles", []): raise HTTPException(403, "approver role required for this tenant")
    return c["sub"]


@app.get("/api/v1/hitl/pending")
async def pending(x_tenant_id: str = Header(), authorization: str | None = Header(default=None)):
    _approver(authorization, x_tenant_id)
    return [{"id": r.id, "tool": r.tool, "args": r.args, "requester": r.requester} for r in hitl.list_pending(x_tenant_id)]


@app.post("/api/v1/hitl/{rid}/{action}")
async def decide(rid: str, action: str, x_tenant_id: str = Header(), authorization: str | None = Header(default=None)):
    who = _approver(authorization, x_tenant_id)
    try:
        if action == "approve":
            hitl.approve(x_tenant_id, rid, who, {"approver"}); return {"state": "APPROVED", "result": await hitl.apply(x_tenant_id, rid)}
        if action == "reject": hitl.reject(x_tenant_id, rid, who, {"approver"}); return {"state": "REJECTED"}
    except HitlError as e: raise HTTPException(409, str(e))
    raise HTTPException(404, "unknown action")
