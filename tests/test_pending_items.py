import time
import httpx
import jwt
import pytest
from assistant.api import TokenBucket, create_app
from assistant.graphify import Graph
from assistant.tracing import Tracer, new_traceparent, parse_traceparent
from mcp_servers.graphify_server import subgraph_tool
from tests.test_api import StubOrch

def client(**kw): return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(StubOrch(), **kw)), base_url="http://t")
B = lambda t="t1": {"tenant_id": t, "user_id": "u", "query": "hi"}
H = lambda t="t1": {"X-Tenant-ID": t}
tok = lambda t, secret="s3cret", exp=3600: jwt.encode({"tenant_id": t, "exp": int(time.time()) + exp}, secret, algorithm="HS256")

def test_traceparent_roundtrip_and_validation():
    tp = new_traceparent(); assert parse_traceparent(tp)
    for bad in (None, "", "00-" + "0" * 32 + "-" + "1" * 16 + "-01", "garbage"): assert parse_traceparent(bad) is None
    tr = Tracer()
    with tr.span("a", tp) as a, tr.span("b", parent=a) as b: pass
    assert a.trace_id == parse_traceparent(tp)[0] and b.trace_id == a.trace_id and b.parent_id == a.span_id and a.ms >= 0

def test_exporter_failure_never_breaks():
    tr = Tracer(exporter=lambda s: 1 / 0)
    with tr.span("x"): pass
    assert len(tr.spans) == 1

async def test_api_propagates_traceparent_header():
    async with client() as c:
        tp = new_traceparent(); r = await c.post("/api/v1/agent/query", json=B(), headers={**H(), "traceparent": tp})
        assert parse_traceparent(r.headers["traceparent"])[0] == parse_traceparent(tp)[0]

async def test_jwt_required_and_tenant_bound():
    async with client(jwt_secret="s3cret") as c:
        assert (await c.post("/api/v1/agent/query", json=B(), headers=H())).status_code == 401
        assert (await c.post("/api/v1/agent/query", json=B(), headers={**H(), "Authorization": "Bearer " + tok("t1", "wrong")})).status_code == 401
        assert (await c.post("/api/v1/agent/query", json=B(), headers={**H(), "Authorization": "Bearer " + tok("t1", exp=-10)})).status_code == 401
        assert (await c.post("/api/v1/agent/query", json=B("t2"), headers={**H("t2"), "Authorization": "Bearer " + tok("t1")})).status_code == 403   # token tenant != body
        assert (await c.post("/api/v1/agent/query", json=B(), headers={**H(), "Authorization": "Bearer " + tok("t1")})).status_code == 200

def test_token_bucket_per_tenant_and_refill():
    t = [0.0]; b = TokenBucket(rate=1, burst=3, clock=lambda: t[0])
    assert [b.allow("a") for _ in range(4)] == [True, True, True, False]
    assert b.allow("b")                                           # other tenant unaffected (noisy-neighbour isolation)
    t[0] = 2.0; assert b.allow("a")

async def test_api_rate_limit_429_isolated_per_tenant():
    async with client(rate_per_s=0.001, burst=2) as c:
        codes = [(await c.post("/api/v1/agent/query", json=B("noisy"), headers=H("noisy"))).status_code for _ in range(4)]
        assert codes == [200, 200, 429, 429]
        assert (await c.post("/api/v1/agent/query", json=B("quiet"), headers=H("quiet"))).status_code == 200

def test_graphify_mcp_tool_contract():
    from transformers import AutoTokenizer
    g, tk = Graph(), AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5"); a = sorted(g.nodes)[5]
    out = subgraph_tool(g, tk, {"tenant_id": "demo", "query": "reciprocal rank fusion constant", "anchors": [a]})
    assert out["tokens"] <= 320 and out["context"]
    assert subgraph_tool(g, tk, {"tenant_id": "demo", "query": "x", "anchors": ["nope"]})["error"]["code"] == "E_NO_ANCHOR"
    for bad in ({"depth": 3}, {"budget": 5}, {"extra": 1}, {"anchors": []}):
        with pytest.raises(Exception): subgraph_tool(g, tk, {"tenant_id": "demo", "query": "x", "anchors": [a], **bad})


def test_agent_registry_consistent_with_code():
    import json
    from pathlib import Path
    from assistant.agent.subagents import EXECUTION_TOOLS, RETRIEVAL_TOOLS
    reg = [json.loads(l[2:]) for l in Path("agents/registry.yaml").read_text().splitlines() if l.startswith("- ")]
    assert len(reg) == 13
    for r in reg:
        assert Path(f"agents/{r['name']}/contract.md").exists()
        if r["status"] == "implemented" and r["implementation"] != "-":
            assert all(Path(p.strip()).exists() for p in r["implementation"].split("+")), r["name"]
    by = {r["name"]: r for r in reg}
    assert set(by["retrieval"]["tools"]) == set(RETRIEVAL_TOOLS) and set(by["execution"]["tools"]) == set(EXECUTION_TOOLS)
    assert not (set(by["retrieval"]["tools"]) & set(by["execution"]["tools"]))


async def test_triage_local_cascade_fast_path_and_llm_deferral():
    import json
    from assistant.agents.triage import Route, TriageAgent
    from assistant.config import Settings
    from assistant.router.providers import FakeProvider
    from assistant.router.router import ModelRouter
    from tests.test_slice3_router import ENV, nosleep
    class L:
        def __init__(self, i, p): self.i, self.p = i, p
        def predict(self, t): return self.i, self.p
    s = Settings.load("/nonexistent", ENV); prov = FakeProvider({"t1p": json.dumps({"intent": "policy_question", "domain": "policy", "risk_tier": 1, "complexity": "low"})})
    mk = lambda l: TriageAgent(ModelRouter(s, prov, sleep=nosleep), local=l)
    r = await mk(L("policy_question", 0.97)).classify("t", "What is the return policy?")
    assert r.source == "local" and r.route == Route.HYBRID_RAG and prov.calls == []              # no LLM call on the fast path
    r = await mk(L("policy_question", 0.60)).classify("t", "What is the return policy?")          # low confidence -> LLM
    assert r.source in ("slm", "slm+rules") and prov.calls
    prov.calls.clear()
    r = await mk(L("transaction", 0.99)).classify("t", "What is the return policy?")              # local says mutate, rules disagree -> LLM
    assert prov.calls and r.route == Route.HYBRID_RAG
    prov.calls.clear()
    r = await mk(L("policy_question", 0.99)).classify("t", "Approve the release of LOT-12345")    # rules say transaction -> never trust local
    assert prov.calls and r.route == Route.TRANSACTION_EXEC
