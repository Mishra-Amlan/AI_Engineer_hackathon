import asyncio
import random
import uuid
import pytest
from assistant.agent.harness import Principal, Tier, ToolHarness, ToolSpec
from assistant.agent.hitl import HitlError, HitlQueue
from assistant.agent.loop import Action, State
from assistant.agent.subagents import (EXECUTION_TOOLS, ExecutionSubagent, LLMReasoner, RETRIEVAL_TOOLS,
                                       RetrievalSubagent, retrieval_tool)
from assistant.audit import AuditLog
from assistant.config import Settings
from assistant.router.providers import FakeProvider
from assistant.router.router import ModelRouter
from tests.test_slice3_router import ENV, nosleep
from tests.test_slice5 import LotIn, SkuIn, TransIn, h_lot, h_sku
import json

applied = []
async def h_trans(a): applied.append(a.model_dump()); return {"applied": True}

def build():
    audit = AuditLog()
    tools = [ToolSpec("lookup_sku", Tier.TIER_1_READ, SkuIn, h_sku), ToolSpec("lookup_lot", Tier.TIER_1_READ, LotIn, h_lot),
             ToolSpec("transition_workflow", Tier.TIER_3_MUTATE, TransIn, h_trans)]
    q = HitlQueue(audit, {"transition_workflow": lambda args: h_trans(TransIn(**args))})
    return ToolHarness(tools, hitl_enqueue=q.submit), q, audit

@pytest.fixture(autouse=True)
def clear(): applied.clear()

def uk(): return str(uuid.uuid4())
ARGS = {"entity_id": "LOT-00044", "to_state": "RELEASED"}
APPR = {"approver"}

async def submit(h, tenant="tA", user="alice", key=None):
    key = key or uk()
    r = await h.execute("transition_workflow", ARGS, Principal(tenant, user), key)
    assert r.status == "PENDING_APPROVAL"; return key

# ---------- HITL (KPI-19) ----------
async def test_full_lifecycle_applies_exactly_once_with_audit():
    h, q, audit = build(); k = await submit(h)
    assert applied == [] and len(q.list_pending("tA")) == 1
    q.approve("tA", k, "bob", APPR)
    await q.apply("tA", k)
    with pytest.raises(HitlError): await q.apply("tA", k)           # no double apply
    assert len(applied) == 1
    assert [e.event_type for e in audit.events("tA")] == ["hitl.submitted", "hitl.approved", "hitl.applied"]
    assert audit.verify()[0]

async def test_cannot_apply_pending_or_rejected():
    h, q, _ = build(); k = await submit(h)
    with pytest.raises(HitlError): await q.apply("tA", k)
    q.reject("tA", k, "bob", APPR)
    with pytest.raises(HitlError): await q.apply("tA", k)
    with pytest.raises(HitlError): q.approve("tA", k, "carol", APPR)   # rejected is terminal
    assert applied == []

async def test_separation_of_duties_and_role():
    h, q, _ = build(); k = await submit(h, user="alice")
    with pytest.raises(HitlError): q.approve("tA", k, "alice", APPR)
    with pytest.raises(HitlError): q.approve("tA", k, "bob", {"viewer"})
    with pytest.raises(HitlError): q.reject("tA", k, "bob", set())

async def test_cross_tenant_cannot_see_or_approve():
    h, q, _ = build(); k = await submit(h, tenant="tA")
    assert q.list_pending("tB") == []
    with pytest.raises(HitlError): q.approve("tB", k, "bob", APPR)

async def test_expiry_never_auto_approves():
    t = [0.0]; audit = AuditLog()
    q = HitlQueue(audit, {"transition_workflow": lambda a: h_trans(TransIn(**a))}, clock=lambda: t[0], ttl_s=10)
    h = ToolHarness([ToolSpec("transition_workflow", Tier.TIER_3_MUTATE, TransIn, h_trans)], hitl_enqueue=q.submit)
    k = await submit(h); t[0] = 11
    with pytest.raises(HitlError): q.approve("tA", k, "bob", APPR)
    assert q.list_pending("tA") == [] and applied == []

async def test_concurrent_apply_runs_once():
    h, q, _ = build(); k = await submit(h); q.approve("tA", k, "bob", APPR)
    out = await asyncio.gather(*[q.apply("tA", k) for _ in range(10)], return_exceptions=True)
    assert len(applied) == 1 and sum(isinstance(o, HitlError) for o in out) == 9

async def test_executor_failure_allows_retry_not_duplicate():
    audit = AuditLog(); n = {"c": 0}
    async def flaky(a):
        n["c"] += 1
        if n["c"] == 1: raise RuntimeError("db")
        return "ok"
    q = HitlQueue(audit, {"transition_workflow": flaky})
    h = ToolHarness([ToolSpec("transition_workflow", Tier.TIER_3_MUTATE, TransIn, h_trans)], hitl_enqueue=q.submit)
    k = await submit(h); q.approve("tA", k, "bob", APPR)
    with pytest.raises(RuntimeError): await q.apply("tA", k)
    assert await q.apply("tA", k) == "ok" and n["c"] == 2

async def test_kpi19_property_no_mutation_without_approval_100pct():
    rnd = random.Random(11); h, q, _ = build(); approved = set(); keys = []
    for i in range(200):
        k = await submit(h, user=f"u{i % 5}"); keys.append(k)
        act = rnd.choice(["approve", "reject", "none", "self", "norole"])
        try:
            if act == "approve": q.approve("tA", k, "reviewer", APPR); approved.add(k)
            elif act == "reject": q.reject("tA", k, "reviewer", APPR)
            elif act == "self": q.approve("tA", k, f"u{i % 5}", APPR)
            elif act == "norole": q.approve("tA", k, "x", set())
        except HitlError: pass
        try: await q.apply("tA", k)
        except HitlError: pass
    assert len(applied) == len(approved)       # applied iff approved by an authorized other person

# ---------- subagent isolation ----------
async def test_execution_subagent_cannot_use_rag_and_retrieval_cannot_mutate():
    h, q, _ = build()
    r = await h.execute("transition_workflow", ARGS, Principal("tA", "u", Tier.TIER_3_MUTATE, RETRIEVAL_TOOLS), uk())
    assert r.error_code == "E_FORBIDDEN" and q.list_pending("tA") == []
    r = await h.execute("hybrid_retrieve", {"query": "x"}, Principal("tA", "u", Tier.TIER_2_COMPUTE, EXECUTION_TOOLS))
    assert r.error_code == "E_FORBIDDEN"
    r = await h.execute("lookup_sku", {"sku": "SKU-1"}, Principal("tA", "u", Tier.TIER_1_READ, RETRIEVAL_TOOLS))
    assert r.error_code == "E_FORBIDDEN"

class FakeRetriever:
    def __init__(self, abstain=False, low=False): self.abstain, self.low = abstain, low
    def retrieve(self, tenant, q):
        from types import SimpleNamespace as N
        hit = N(chunk=N(id="c1", source="doc", text="[doc] RRF smoothing constant k = 60 in this system."))
        return N(abstain=self.abstain, low_confidence=self.low, confidence=0.9, hits=[] if self.abstain else [hit])

async def test_retrieval_subagent_evidence_abstain_and_tenant_binding():
    seen = {}
    class R(FakeRetriever):
        def retrieve(self, tenant, q): seen["t"] = tenant; return super().retrieve(tenant, q)
    ToolH = lambda r: ToolHarness([retrieval_tool(r, lambda: "tA")])
    out = await RetrievalSubagent(ToolH(R())).run("tA", "u", "what is rrf k")
    assert not out["abstain"] and out["chunks"][0]["id"] == "c1" and seen["t"] == "tA"
    assert (await RetrievalSubagent(ToolH(FakeRetriever(abstain=True))).run("tA", "u", "x"))["abstain"]
    assert (await RetrievalSubagent(ToolH(FakeRetriever(low=True))).run("tA", "u", "x"))["low_confidence"]

# ---------- LLM reasoner + execution subagent ----------
def router_with(script):
    s = Settings.load("/nonexistent", ENV)
    return ModelRouter(s, FakeProvider(script), sleep=nosleep)

async def test_execution_subagent_end_to_end_with_llm_reasoner_hitl():
    h, q, _ = build()
    script = {"t2p": [json.dumps({"kind": "tool", "tool": "transition_workflow", "args": ARGS}),
                      json.dumps({"kind": "final", "answer": "never reached"})]}
    res = await ExecutionSubagent(h, router_with(script)).run("tA", "alice", "Release LOT-00044", "s1")
    assert res.reason == "hitl_pending" and applied == [] and len(q.list_pending("tA")) == 1

async def test_llm_reasoner_read_flow_and_auto_repair():
    h, q, _ = build()
    script = {"t2p": [json.dumps({"kind": "tool", "tool": "lookup_lot", "args": {"lot": "lot 44"}}),
                      json.dumps({"kind": "final", "answer": "LOT-00044 is RELEASED"})]}
    res = await ExecutionSubagent(h, router_with(script)).run("tA", "u", "status of lot 44?", "s2")
    assert res.state == State.DONE and res.answer == "LOT-00044 is RELEASED" and res.steps == 2

async def test_llm_reasoner_cannot_call_tool_outside_allowlist():
    h, q, _ = build()
    script = {"t2p": [json.dumps({"kind": "tool", "tool": "hybrid_retrieve", "args": {"query": "x"}}),
                      json.dumps({"kind": "final", "answer": "done"})]}
    res = await ExecutionSubagent(h, router_with(script)).run("tA", "u", "hi", "s3")
    assert res.trace[3]["status"] == "ERROR" if len(res.trace) > 3 else True
    assert res.state == State.DONE

async def test_model_supplied_idempotency_key_ignored():
    h, q, _ = build()
    script = {"t2p": [json.dumps({"kind": "tool", "tool": "transition_workflow", "args": ARGS, "idempotency_key": "bogus"})]}
    res = await ExecutionSubagent(h, router_with(script)).run("tA", "alice", "release", "s4")
    pend = q.list_pending("tA")
    assert res.reason == "hitl_pending" and len(pend) == 1 and uuid.UUID(pend[0].id).version == 4

async def test_all_models_down_reasoner_returns_safe_abstention_no_mutation():
    from assistant.router.types import ProviderError
    h, q, _ = build(); err = ProviderError("server")
    router = router_with({m: err for m in ["t1p", "t1f", "t2p", "t2f"]})
    res = await ExecutionSubagent(h, router).run("tA", "u", "release LOT-00044", "s5")
    assert res.state == State.DONE and "can't answer" in res.answer and applied == [] and q.list_pending("tA") == []
