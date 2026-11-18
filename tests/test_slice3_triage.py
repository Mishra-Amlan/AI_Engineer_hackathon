import json
from assistant.agents.triage import Route, TriageAgent, rules_classify, route_for
from assistant.config import Settings
from assistant.router.providers import FakeProvider
from assistant.router.router import ModelRouter
from assistant.router.types import ProviderError
from tests.test_slice3_router import ENV, nosleep

# (query, expected route)  — labeled set (KPI-04)
LABELED = [
    ("hello", Route.DIRECT_ANSWER), ("Thanks!", Route.DIRECT_ANSWER), ("who are you?", Route.DIRECT_ANSWER),
    ("What is the return policy for damaged goods?", Route.HYBRID_RAG),
    ("How do I handle a cold-chain deviation per the SOP?", Route.HYBRID_RAG),
    ("What are the compliance requirements for batch release?", Route.HYBRID_RAG),
    ("Verify batch LOT-88392 safety protocol and return triage status", Route.HYBRID_RAG),
    ("Is SKU-099 in stock?", Route.HYBRID_RAG), ("What is the status of LOT-00044?", Route.HYBRID_RAG),
    ("List all SKUs in the active catalog", Route.HYBRID_RAG), ("How many units of SKU-120 do we have?", Route.HYBRID_RAG),
    ("Compare the quarantine policy across sites", Route.HYBRID_RAG),
    ("Approve the release of LOT-12345", Route.TRANSACTION_EXEC), ("Move SKU-099 to quarantine", Route.TRANSACTION_EXEC),
    ("Cancel order 5521 and update the workflow", Route.TRANSACTION_EXEC), ("Mark batch LOT-77777 as recalled", Route.TRANSACTION_EXEC),
    ("Delete shipment 889", Route.TRANSACTION_EXEC), ("Update the status of SKU-045 to discontinued", Route.TRANSACTION_EXEC),
    ("what's the weather in Paris", Route.REJECT_OOS), ("write me a poem about autumn", Route.REJECT_OOS),
    ("tell me a joke", Route.REJECT_OOS), ("what is the bitcoin price", Route.REJECT_OOS),
    ("Can SKU-099 be shipped without approval, per policy?", Route.HYBRID_RAG),
    ("How do I update a batch record according to the SOP?", Route.HYBRID_RAG),
]

def test_rules_routing_accuracy_kpi04():
    wrong = [(q, route_for(rules_classify(q)).value, e.value) for q, e in LABELED if route_for(rules_classify(q)) != e]
    assert 1 - len(wrong) / len(LABELED) >= 0.97, wrong

def agent(script):
    s = Settings.load("/nonexistent", ENV)
    return TriageAgent(ModelRouter(s, FakeProvider(script), sleep=nosleep))

def js(**k): return json.dumps({"intent": "policy_question", "domain": "policy", "risk_tier": 1, "complexity": "low", **k})

async def test_slm_result_used():
    r = await agent({"t1p": js()}).classify("t", "What is the return policy?")
    assert r.source == "slm" and r.route == Route.HYBRID_RAG and r.model == "t1p"

async def test_rules_raise_risk_when_slm_underrates_mutation():
    r = await agent({"t1p": js()}).classify("t", "Approve the release of LOT-12345")
    assert r.route == Route.TRANSACTION_EXEC and r.risk_tier == 3 and r.source == "slm+rules"

async def test_slm_cannot_be_lowered_by_rules_and_tier3_always_executes_via_hitl_route():
    r = await agent({"t1p": js(intent="transaction", risk_tier=3)}).classify("t", "hello there")
    assert r.route == Route.TRANSACTION_EXEC          # rules never lower risk

async def test_route_is_not_taken_from_model():
    r = await agent({"t1p": json.dumps({"intent": "lookup", "domain": "inventory", "risk_tier": 1,
                                        "complexity": "low", "route": "TRANSACTION_EXEC"})}).classify("t", "Is SKU-099 in stock?")
    assert r.route == Route.HYBRID_RAG

async def test_fallback_to_rules_when_all_models_fail():
    err = ProviderError("server")
    r = await agent({"t1p": err, "t1f": err}).classify("t", "Approve the release of LOT-12345")
    assert r.source == "rules" and r.route == Route.TRANSACTION_EXEC

async def test_garbage_model_output_falls_back_to_rules():
    r = await agent({"t1p": "lol", "t1f": "{}"}).classify("t", "tell me a joke")
    assert r.source == "rules" and r.route == Route.REJECT_OOS

async def test_invalid_enum_from_model_rejected():
    r = await agent({"t1p": js(risk_tier=9), "t1f": js(risk_tier=9)}).classify("t", "hello")
    assert r.source == "rules"

async def test_oos_rule_overrides_slm_policy_guess():
    r = await agent({"t1p": js()}).classify("t", "tell me a joke")
    assert r.route == Route.REJECT_OOS

async def test_rules_only_mode_no_provider_calls():
    s = Settings.load("/nonexistent", ENV); p = FakeProvider()
    a = TriageAgent(ModelRouter(s, p, sleep=nosleep), use_model=False)
    assert (await a.classify("t", "hello")).route == Route.DIRECT_ANSWER and p.calls == []

async def test_triage_latency_kpi05_overhead_only():
    import time
    a = agent({"t1p": js()}); lat = []
    for _ in range(200):
        t0 = time.perf_counter(); await a.classify("t", "What is the return policy?"); lat.append((time.perf_counter()-t0)*1000)
    lat.sort(); assert lat[190] <= 25   # code overhead only; live-model latency measured in smoke test
