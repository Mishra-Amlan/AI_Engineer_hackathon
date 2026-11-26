"""Request path: pre-hooks -> triage -> route -> (retrieval -> generation -> verification | execution | canned) -> audit.
Everything downstream of the pre-hooks sees only PII-redacted text."""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from .agent.generation import GenerationPipeline
from .agent.subagents import ExecutionSubagent, RetrievalSubagent
from .agents.triage import Route, TriageAgent
from .audit import AuditLog
from .plugins.base import PluginManager, RequestContext, Stage
import re
from .tenancy import validate_tenant_id

_ENTITY_ID = re.compile(r"\b(?:sku|lot)[\s_-]?\d{1,5}\b", re.I)

REFUSAL = "I can't help with that request."
OOS = "That's outside what I can help with. I can answer policy questions and look up SKU/LOT information."
HELLO = "Hello! I can answer questions about our policies and look up SKU/LOT status."


@dataclass
class Response:
    text: str
    route: str
    request_id: str
    abstained: bool = False
    blocked: bool = False
    citations: list[dict] = field(default_factory=list)
    pending_approval: bool = False
    mode: str = ""
    spans_ms: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    retrieved_ids: list[str] = field(default_factory=list)


class Orchestrator:
    def __init__(self, plugins: PluginManager, triage: TriageAgent, retrieval: RetrievalSubagent,
                 generation: GenerationPipeline, execution: ExecutionSubagent, audit: AuditLog, cache=None):
        self.cache = cache
        self.plugins, self.triage, self.retrieval, self.gen, self.exec, self.audit = plugins, triage, retrieval, generation, execution, audit

    async def handle(self, tenant_id: str, user_id: str, text: str, session: str = "s") -> Response:
        validate_tenant_id(tenant_id)
        rid, spans, t0 = str(uuid.uuid4()), {}, time.perf_counter()
        def span(name, t): spans[name] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        ctx = self.plugins.run_stage(Stage.PRE_EXECUTION, RequestContext(tenant_id, user_id, text, rid))
        span("hook.pre", t)
        if ctx.blocked:
            self.audit.append(tenant_id, "request.blocked", {"rid": rid, "reason": ctx.block_reason, "findings": ctx.findings})
            return Response(REFUSAL, "BLOCKED", rid, blocked=True, spans_ms=spans)
        clean = ctx.text                                    # PII-redacted from here on
        self.audit.append(tenant_id, "request.accepted", {"rid": rid, "text": clean, "findings": ctx.findings})

        t = time.perf_counter()
        hit = self.cache.lookup(tenant_id, user_id, clean) if self.cache else None
        span("cache.lookup", t)
        if hit is not None:
            return self._done(tenant_id, rid, Response(hit["text"], hit["route"], rid, citations=hit["citations"], mode="cache_hit"), spans, t0)

        t = time.perf_counter()
        tri = await self.triage.classify(tenant_id, clean)
        span("triage.classify", t)
        self.audit.append(tenant_id, "triage", {"rid": rid, "route": tri.route.value, "risk": tri.risk_tier, "source": tri.source})

        if tri.route == Route.REJECT_OOS: return self._done(tenant_id, rid, Response(OOS, tri.route.value, rid, mode="canned"), spans, t0)
        if tri.route == Route.DIRECT_ANSWER: return self._done(tenant_id, rid, Response(HELLO, tri.route.value, rid, mode="canned"), spans, t0)

        # read-only SKU/LOT lookups are answered from the state-store (execution subagent, Tier-1 tools), not from documents
        is_lookup = tri.route == Route.HYBRID_RAG and tri.intent == "lookup" and bool(_ENTITY_ID.search(clean))
        if tri.route == Route.TRANSACTION_EXEC or is_lookup:
            t = time.perf_counter()
            res = await self.exec.run(tenant_id, user_id, clean, session)
            span("agent.execution", t)
            pend = res.reason == "hitl_pending"
            ans = res.answer or "I couldn't complete that request safely. A human operator has been notified."
            return self._done(tenant_id, rid, Response(ans, "STATE_LOOKUP" if is_lookup else tri.route.value, rid, pending_approval=pend, mode=res.state.value,
                                                       abstained=res.state.value.startswith("HALTED")), spans, t0)

        t = time.perf_counter()
        ev = await self.retrieval.run(tenant_id, user_id, clean)
        span("agent.retrieval", t)
        t = time.perf_counter()
        g = await self.gen.run(tenant_id, clean, ev["chunks"], ev.get("low_confidence", False))
        span("llm.generate+verify", t)
        cites = [{"n": n, "id": ev["chunks"][n - 1]["id"], "source": ev["chunks"][n - 1]["source"]} for n in g.citations]
        self.audit.append(tenant_id, "answer", {"rid": rid, "mode": g.mode, "verified": g.verified, "cites": [c["id"] for c in cites],
                                                "unsupported": g.unsupported[:3], "llm_calls": g.llm_calls})
        resp = Response(g.answer, tri.route.value, rid, abstained=g.mode == "abstain", citations=cites, mode=g.mode, cost_usd=g.cost_usd,
                    retrieved_ids=[c["id"] for c in ev["chunks"]])
        # cache only verified, generated, non-low-confidence policy answers (never abstentions, fallbacks, transactions)
        if self.cache and g.mode in ("generated", "regenerated") and g.verified and not ev.get("low_confidence"):
            self.cache.store(tenant_id, user_id, clean, {"text": g.answer, "route": tri.route.value, "citations": cites})
        return self._done(tenant_id, rid, resp, spans, t0)

    def _done(self, tenant_id, rid, resp: Response, spans, t0) -> Response:
        spans["total"] = (time.perf_counter() - t0) * 1000
        resp.spans_ms = spans
        self.audit.append(tenant_id, "response", {"rid": rid, "route": resp.route, "mode": resp.mode, "abstained": resp.abstained})
        return resp
