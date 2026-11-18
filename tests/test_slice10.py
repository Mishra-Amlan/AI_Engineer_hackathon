import pytest
from assistant.cache import SemanticCache
from assistant.release import ArtifactRegistry, FlagService, Guardrails, RolloutController
from tests.test_slice4_unit import FakeEmb

def reg():
    r = ArtifactRegistry(); r.register("rerank_threshold", "v1", {"t": 0.42}); r.register("rerank_threshold", "v2", {"t": 0.55}); r.activate("rerank_threshold", "v1"); return r

def test_artifacts_immutable_versioned_with_digest_and_snapshot():
    r = reg()
    with pytest.raises(ValueError): r.register("rerank_threshold", "v1", {"t": 0.1})
    a = r.active("rerank_threshold"); assert a.content == {"t": 0.42} and r.snapshot()["rerank_threshold"].startswith("v1@")
    r.activate("rerank_threshold", "v2"); assert r.active("rerank_threshold").content["t"] == 0.55
    assert r.rollback("rerank_threshold") == "v1" and r.active("rerank_threshold").content["t"] == 0.42
    with pytest.raises(RuntimeError): r.rollback("rerank_threshold")

def test_guardrail_plugins_cannot_be_flagged_off_even_if_backend_says_so():
    f = FlagService(fetch=lambda: {"pii_redactor": {"enabled": False, "percent": 0}})
    assert f.is_on("pii_redactor", "t") and f.is_on("injection_shield", "t")
    with pytest.raises(PermissionError): f.set("pii_redactor", False)

def test_flag_percent_sticky_and_roughly_uniform():
    f = FlagService(); f.set("new_rerank", True, 25)
    on = [f.is_on("new_rerank", f"tenant_{i}") for i in range(2000)]
    assert 0.20 < sum(on) / 2000 < 0.30 and on == [f.is_on("new_rerank", f"tenant_{i}") for i in range(2000)]
    f.set("new_rerank", False); assert not any(f.is_on("new_rerank", f"tenant_{i}") for i in range(100))

def test_flag_backend_outage_uses_last_known_good():
    state = {"up": True}
    def fetch():
        if not state["up"]: raise ConnectionError
        return {"x": {"enabled": True, "percent": 100}}
    f = FlagService(fetch); assert f.is_on("x", "t"); state["up"] = False
    assert f.is_on("x", "t") and not f.is_on("unknown", "t")

def test_healthy_rollout_reaches_100():
    r = reg(); f = FlagService(); calls = []
    res = RolloutController(f, r).rollout("t55", "rerank_threshold", "v2", lambda p: (calls.append(p), {"p95_ms": 400, "faithfulness": 0.95})[1])
    assert not res.rolled_back and res.final_percent == 100 and calls == [1, 5, 25, 100] and r.active("rerank_threshold").version == "v2"

@pytest.mark.parametrize("bad,name", [({"p95_ms": 700}, "p95_ms"), ({"faithfulness": 0.8}, "faithfulness"), ({"err_5xx": 0.01}, "err_5xx"),
                                       ({"cross_tenant_leaks": 1}, "cross_tenant_leaks"), ({"hitl_bypass": 1}, "hitl_bypass")])
def test_auto_rollback_on_each_guardrail_breach(bad, name):
    r = reg(); f = FlagService(); purged = []
    res = RolloutController(f, r, on_rollback=lambda: purged.append(1)).rollout(
        "t55", "rerank_threshold", "v2", lambda p: bad if p == 25 else {"p95_ms": 300, "faithfulness": 0.95})
    assert res.rolled_back and name in res.breaches and res.history[-1][0] == 25 and res.final_percent == 0
    assert r.active("rerank_threshold").version == "v1" and not f.is_on("t55", "tenant_1") and purged == [1]
    assert res.rollback_seconds < 300            # X-04 (<=5 min); in-process flip is milliseconds

def test_rollback_invalidates_semantic_cache():
    c = SemanticCache(FakeEmb(), version="v2"); c.store("t", "u", "q", {"a": 1}); assert c.lookup("t", "u", "q")
    r = reg(); RolloutController(FlagService(), r, on_rollback=lambda: c.bump_version("v1")).rollout("f", "rerank_threshold", "v2", lambda p: {"p95_ms": 9999})
    assert c.lookup("t", "u", "q") is None
