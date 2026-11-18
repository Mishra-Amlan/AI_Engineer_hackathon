import asyncio
import numpy as np
import pytest
from assistant.cache import SemanticCache
from tests.test_slice4_unit import FakeEmb
from tests.test_slice7 import GOOD, OK_V, orch

class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t

def mk(clk=None, **kw): return SemanticCache(FakeEmb(), clock=clk or Clock(), **kw)

def test_exact_and_semantic_hit_within_tenant():
    c = mk(threshold=0.9)
    c.store("tA", "u1", "what is the rrf smoothing constant", {"a": 1})
    assert c.lookup("tA", "u1", "  What is the RRF smoothing   constant ") == {"a": 1}          # exact (normalized)
    assert c.lookup("tA", "u2", "what is the rrf smoothing constant") == {"a": 1}             # other user: semantic path
    assert c.lookup("tA", "u1", "sourdough bread flour recipe") is None
    assert c.stats["hit_exact"] == 1 and c.stats["hit_semantic"] == 1 and c.stats["miss"] == 1

def test_cross_tenant_isolation_exact_and_semantic():
    c = mk(threshold=0.5)
    c.store("tA", "u", "secret policy about rrf", {"owner": "A"})
    assert c.lookup("tB", "u", "secret policy about rrf") is None
    assert c.lookup("tB", "u", "policy rrf secret") is None
    assert c.lookup("tA", "u", "policy rrf secret") == {"owner": "A"}

def test_kpi28_probe_many_tenants_zero_leaks():
    c = mk(threshold=0.8)
    for i in range(200): c.store(f"tenant_{i}", "u", "shared question text", {"t": i})
    leaks = sum(c.lookup(f"tenant_{i}", "u", "shared question text")["t"] != i for i in range(200))
    assert leaks == 0

def test_ttl_expiry_with_jitter_and_version_invalidation():
    clk = Clock(); c = mk(clk, ttl=300, jitter=45)
    c.store("t", "u", "q one", {"v": 1})
    clk.t = 254; assert c.lookup("t", "u", "q one") is not None          # >= 255 s always alive? (min ttl 255) -> alive at 254
    clk.t = 346; assert c.lookup("t", "u", "q one") is None              # > 345 s always dead
    c.store("t", "u", "q two", {"v": 2}); c.bump_version("v2")
    assert c.lookup("t", "u", "q two") is None                           # rollback/new index => stale entries unreadable

def test_lru_cap_per_tenant():
    c = mk(max_per_tenant=3)
    for i in range(10): c.store("t", "u", f"distinct question number {i} alpha{i}", {"i": i})
    assert len(c._ns[next(iter(c._ns))]) == 3

async def test_single_flight_stampede_one_compute():
    c = mk(); n = {"c": 0}
    async def compute():
        n["c"] += 1; await asyncio.sleep(0.05); return {"x": 1}, True
    out = await asyncio.gather(*[c.get_or_compute("t", "u", "same question", compute) for _ in range(100)])
    assert n["c"] == 1 and all(v == {"x": 1} for v, _ in out)

async def test_single_flight_error_propagates_and_clears():
    c = mk()
    async def bad(): raise RuntimeError("x")
    for _ in range(2):
        with pytest.raises(RuntimeError): await c.get_or_compute("t", "u", "q", bad)
    assert not c._inflight

async def test_orchestrator_second_identical_question_is_cache_hit_no_llm():
    o, prov, audit, _ = orch({"t2p": GOOD, "v": OK_V})
    o.cache = mk(threshold=0.9)
    r1 = await o.handle("tA", "u", "What is the RRF smoothing constant policy?")
    calls = len(prov.calls)
    r2 = await o.handle("tA", "u2", "what is the RRF smoothing constant policy")
    assert r1.mode == "generated" and r2.mode == "cache_hit" and r2.text == r1.text and len(prov.calls) == calls
    r3 = await o.handle("tB", "u", "What is the RRF smoothing constant policy?")
    assert r3.mode != "cache_hit"                                                    # other tenant never served from tA cache

async def test_abstentions_and_transactions_not_cached():
    from tests.test_slice6 import FakeRetriever
    o, prov, _, _ = orch({"t2p": GOOD}, retriever=FakeRetriever(abstain=True)); o.cache = mk()
    await o.handle("tA", "u", "What is the CEO salary policy?")
    assert o.cache.lookup("tA", "u", "What is the CEO salary policy?") is None
    o2, *_ = orch({"t2p": GOOD, "v": OK_V}, retriever=FakeRetriever(low=True)); o2.cache = mk()
    await o2.handle("tA", "u", "What is the RRF smoothing constant policy?")
    assert o2.cache.lookup("tA", "u", "What is the RRF smoothing constant policy?") is None   # low-confidence answers never cached
