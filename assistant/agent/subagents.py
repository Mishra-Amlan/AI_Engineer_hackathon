"""Scoped subagents. Allowlists are enforced by the harness via Principal.allowed_tools."""
from __future__ import annotations
import asyncio
import uuid
from pydantic import BaseModel, ConfigDict, Field
from ..router.router import ModelRouter
from ..router.types import Message, RouterRequest, Tier
from .harness import Principal, Tier as ToolTier, ToolHarness, ToolSpec
from .loop import Action, ReActLoop, State

RETRIEVAL_TOOLS = frozenset({"hybrid_retrieve"})
EXECUTION_TOOLS = frozenset({"lookup_sku", "lookup_lot", "transition_workflow"})   # state-store only: no RAG / web


class RetrieveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)


def retrieval_tool(retriever, tenant_id_getter, timeout_s: float | None = None) -> ToolSpec:
    async def handler(a: RetrieveIn):
        res = await asyncio.to_thread(retriever.retrieve, tenant_id_getter(), a.query)
        return {"abstain": res.abstain, "low_confidence": res.low_confidence, "confidence": res.confidence,
                "chunks": [{"id": h.chunk.id, "source": h.chunk.source, "text": h.chunk.text} for h in res.hits]}
    return ToolSpec("hybrid_retrieve", ToolTier.TIER_1_READ, RetrieveIn, handler, timeout_s)


class RetrievalSubagent:
    """Read-only. Deterministic pipeline: retrieve -> (abstain | cited extractive evidence)."""
    def __init__(self, harness: ToolHarness):
        self.h = harness

    def principal(self, tenant_id, user_id): return Principal(tenant_id, user_id, ToolTier.TIER_1_READ, RETRIEVAL_TOOLS)

    async def run(self, tenant_id: str, user_id: str, query: str) -> dict:
        r = await self.h.execute("hybrid_retrieve", {"query": query}, self.principal(tenant_id, user_id))
        if not r.ok: return {"abstain": True, "reason": r.error_code, "chunks": []}
        d = r.data
        if d["abstain"] or not d["chunks"]: return {"abstain": True, "reason": "low_retrieval_confidence", "chunks": []}
        return {"abstain": False, "low_confidence": d["low_confidence"], "chunks": d["chunks"], "confidence": d["confidence"]}


class ActionModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str = Field(pattern="^(tool|final)$")
    tool: str = ""
    args: dict = {}
    answer: str = ""


class LLMReasoner:
    """Model-backed reasoner via the Router (T2, temp 0, schema-validated). The model never supplies idempotency keys."""
    def __init__(self, router: ModelRouter, tenant_id: str, tools: dict[str, ToolSpec], allowed: frozenset[str]):
        self.router, self.tenant, self.allowed = router, tenant_id, allowed
        self.tools = {n: t for n, t in tools.items() if n in allowed}

    def _catalog(self) -> str:
        return "\n".join(f"- {n}: args {t.model.model_json_schema().get('properties', {})}" for n, t in self.tools.items())

    async def __call__(self, prompt: list[dict]) -> Action:
        sys = ("You operate a ReAct loop. Reply ONLY JSON: {\"kind\":\"tool\",\"tool\":NAME,\"args\":{...}} or "
               "{\"kind\":\"final\",\"answer\":TEXT}. Use only these tools:\n" + self._catalog() +
               "\nNever invent data. Base the final answer only on tool observations.")
        msgs = [Message(role="system", content=sys)] + [Message(role=m["role"], content=m["content"]) for m in prompt]
        r = await self.router.complete(RouterRequest(tenant_id=self.tenant, tier=Tier.T2, messages=msgs, json_schema=ActionModel,
                                                     temperature=0.0, max_tokens=200, purpose="react"))
        if r.abstained or not r.parsed:
            return Action("final", answer=r.text)                           # router already produced the safe abstention
        a = ActionModel(**r.parsed)
        if a.kind == "final": return Action("final", answer=a.answer)
        spec = self.tools.get(a.tool)
        key = str(uuid.uuid4()) if spec and spec.tier == ToolTier.TIER_3_MUTATE else None
        return Action("tool", a.tool, a.args, idempotency_key=key)


class ExecutionSubagent:
    """State-store tools only. Tier-3 -> HITL freeze."""
    def __init__(self, harness: ToolHarness, router: ModelRouter | None = None, reasoner=None, **loop_kwargs):
        # loop_kwargs e.g. total_budget_ms: spec default 450 ms assumes a local SLM; remote LLMs need a dev override
        self.h, self.router, self._reasoner, self.loop_kwargs = harness, router, reasoner, loop_kwargs

    async def run(self, tenant_id: str, user_id: str, text: str, session: str, reasoner=None):
        who = Principal(tenant_id, user_id, ToolTier.TIER_2_COMPUTE, EXECUTION_TOOLS)
        rz = reasoner or self._reasoner or LLMReasoner(self.router, tenant_id, self.h.tools, EXECUTION_TOOLS)
        return await ReActLoop(rz, self.h, **self.loop_kwargs).run(who, session, text)
