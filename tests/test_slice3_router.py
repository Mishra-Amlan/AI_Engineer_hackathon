import asyncio
import pytest
from pydantic import BaseModel
from assistant.config import Settings
from assistant.router.breaker import CircuitBreaker
from assistant.router.providers import FakeProvider
from assistant.router.router import ModelRouter
from assistant.router.types import (ABSTAIN_TEXT, Message, ProviderError, RouterRequest, Tier)

ENV = {"OPENROUTER_API_KEY": "k", "MODEL_T1_PRIMARY": "t1p", "MODEL_T1_FALLBACK": "t1f",
       "MODEL_T2_PRIMARY": "t2p", "MODEL_T2_FALLBACK": "t2f", "MODEL_T3_PRIMARY": "t3p",
       "MODEL_T3_FALLBACK": "t3f", "MODEL_VERIFIER": "v", "ROUTER_RETRY_BACKOFF_MS": "0"}

class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t

async def nosleep(_): return None

def mk(script=None, env=None, clock=None):
    s = Settings.load("/nonexistent", {**ENV, **(env or {})})
    p = FakeProvider(script)
    return ModelRouter(s, p, clock=clock or Clock(), sleep=nosleep), p

def req(tier=Tier.T2, **kw):
    return RouterRequest(tenant_id="t", tier=tier, messages=[Message(role="user", content="hi")], **kw)

async def test_happy_path_primary():
    r, p = mk({"t2p": "answer"})
    out = await r.complete(req())
    assert out.text == "answer" and out.model == "t2p" and not out.degraded and p.calls == ["t2p"]

async def test_retry_once_then_success_same_model():
    r, p = mk({"t2p": [ProviderError("rate_limit"), "ok"]})
    out = await r.complete(req())
    assert out.model == "t2p" and p.calls == ["t2p", "t2p"] and out.attempts == 2

async def test_429_storm_falls_back_to_secondary_same_tier():
    r, p = mk({"t2p": ProviderError("rate_limit")})
    out = await r.complete(req())
    assert out.model == "t2f" and out.degraded and out.fallback_depth == 1
    assert p.calls.count("t2p") == 2          # max 1 retry

async def test_whole_tier_down_drops_to_lower_tier():
    r, p = mk({"t2p": ProviderError("server"), "t2f": ProviderError("server")})
    out = await r.complete(req())
    assert out.tier_used == Tier.T1 and out.degraded and out.model == "t1p"

async def test_all_down_abstains_never_fails_open():
    err = ProviderError("server")
    r, p = mk({m: err for m in ["t1p", "t1f", "t2p", "t2f"]})
    out = await r.complete(req())
    assert out.abstained and out.text == ABSTAIN_TEXT and out.model is None
    assert len(p.calls) <= 8   # bounded hops

async def test_extractive_fallback_before_abstain():
    err = ProviderError("timeout")
    r, _ = mk({m: err for m in ["t1p", "t1f", "t2p", "t2f"]})
    out = await r.complete(req(extractive_fallback="Returns accepted within 30 days."))
    assert not out.abstained and out.text.startswith("Returns") and out.reason.startswith("extractive")

async def test_breaker_opens_and_skips_model():
    r, p = mk({"t2p": ProviderError("server")})
    await r.complete(req()); p.calls.clear()
    out = await r.complete(req())
    assert "t2p" not in p.calls and out.model == "t2f"

async def test_breaker_half_open_recovers():
    clk = Clock()
    r, p = mk({"t2p": [ProviderError("server"), ProviderError("server")]}, clock=clk)
    await r.complete(req())                 # opens t2p breaker (threshold 2)
    clk.t += 31
    out = await r.complete(req())           # half-open probe succeeds (script drained -> default)
    assert out.model == "t2p" and r.breakers["t2p"].state == "closed"

def test_breaker_unit():
    c = Clock(); b = CircuitBreaker(2, 10, c)
    b.failure(); assert b.allow()
    b.failure(); assert b.state == "open" and not b.allow()
    c.t = 11; assert b.state == "half_open" and b.allow() and not b.allow()   # single probe
    b.failure(); assert b.state in ("open", "half_open")

async def test_auth_error_trips_model_no_retry_but_ladder_continues():
    r, p = mk({"t2p": ProviderError("auth")})
    out = await r.complete(req())
    assert p.calls.count("t2p") == 1 and out.model == "t2f" and r.breakers["t2p"].state == "open"

async def test_model_unavailable_skips_without_retry():
    r, p = mk({"t2p": ProviderError("model_unavailable")})
    out = await r.complete(req())
    assert p.calls.count("t2p") == 1 and out.model == "t2f"

class Out(BaseModel):
    label: str

async def test_schema_ok_parses_fenced_json():
    r, _ = mk({"t1p": '```json\n{"label": "x"}\n```'})
    out = await r.complete(req(Tier.T1, json_schema=Out))
    assert out.parsed == {"label": "x"}

async def test_schema_bad_output_retries_then_falls_back():
    r, p = mk({"t1p": "not json", "t1f": '{"label":"y"}'})
    out = await r.complete(req(Tier.T1, json_schema=Out))
    assert out.model == "t1f" and out.parsed == {"label": "y"} and p.calls.count("t1p") == 2

async def test_schema_never_returns_unvalidated():
    r, _ = mk({m: "garbage" for m in ["t1p", "t1f"]})
    out = await r.complete(req(Tier.T1, json_schema=Out))
    assert out.abstained and out.parsed is None

async def test_empty_output_treated_as_failure():
    r, _ = mk({"t2p": "  ", "t2f": "real"})
    assert (await r.complete(req())).model == "t2f"

async def test_deadline_stops_ladder():
    clk = Clock()
    class Slow(FakeProvider):
        async def complete(self, *a, **k):
            clk.t += 5; raise ProviderError("server")
    s = Settings.load("/nonexistent", ENV)
    r = ModelRouter(s, Slow(), clock=clk, sleep=nosleep)
    out = await r.complete(req(deadline_ms=4000))
    assert out.abstained and out.reason in ("deadline", "ladder_exhausted")

async def test_real_timeout_enforced():
    class Hang(FakeProvider):
        async def complete(self, *a, **k): await asyncio.sleep(5)
    s = Settings.load("/nonexistent", {**ENV, "ROUTER_REQUEST_TIMEOUT_MS": "50", "ROUTER_MAX_RETRIES": "0"})
    r = ModelRouter(s, Hang(), sleep=nosleep)
    out = await asyncio.wait_for(r.complete(req(deadline_ms=400)), 3)
    assert out.abstained

async def test_tenant_budget_blocks_then_abstains():
    r, p = mk({"t2p": "ok"}, env={"PER_TENANT_DAILY_BUDGET_USD": "0.0"})
    out = await r.complete(req())
    assert out.abstained and p.calls == [] and "budget" in str(out.trace)

async def test_budget_isolated_per_tenant():
    r, _ = mk(env={"PER_TENANT_DAILY_BUDGET_USD": "0.003"})
    for _ in range(60): await r.complete(req())
    a = r.budget.tenant_spent["t"]
    out = await r.complete(RouterRequest(tenant_id="other", tier=Tier.T2, messages=[Message(role="user", content="hi")]))
    assert 0 < a <= 0.003 and not out.abstained

async def test_cost_recorded():
    r, _ = mk({"t2p": "ok"})
    out = await r.complete(req())
    assert out.cost_usd > 0 and r.budget.global_spent == out.cost_usd

async def test_escalation_limit():
    r, _ = mk()
    ok = await r.complete(req(Tier.T1, escalations=1))
    assert ok.tier_requested == Tier.T2 and not ok.abstained
    bad = await r.complete(req(Tier.T1, escalations=2))
    assert bad.abstained and bad.reason == "escalation_limit"

async def test_t0_rejected():
    r, _ = mk()
    with pytest.raises(ValueError):
        await r.complete(req(Tier.T0))

async def test_ladder_bounded_hops_under_total_failure_fault_injection():
    r, p = mk({m: ProviderError("rate_limit") for m in ["t1p", "t1f", "t2p", "t2f", "t3p", "t3f"]})
    out = await r.complete(req(Tier.T3))
    assert out.abstained and len(p.calls) <= 12

async def test_concurrent_requests_isolated():
    r, _ = mk({"t2p": "ok"})
    outs = await asyncio.gather(*[r.complete(req()) for _ in range(100)])
    assert all(o.text == "ok" and o.latency_ms >= 0 for o in outs)


async def test_multiprovider_dispatch_and_prefix_stripped():
    from assistant.router.providers import MultiProvider
    a, b = FakeProvider(default="or"), FakeProvider(default="gq")
    mp = MultiProvider(a, {"groq": b})
    m = [Message(role="user", content="x")]
    assert (await mp.complete("groq:openai/gpt-oss-120b", m, 5, 0, 5, False)).text == "gq" and b.calls == ["openai/gpt-oss-120b"]
    assert (await mp.complete("meta/x", m, 5, 0, 5, False)).text == "or"

async def test_groq_without_key_is_fatal_auth_not_silent_openrouter():
    from assistant.router.providers import MultiProvider
    r, _ = mk()
    r.provider = MultiProvider(FakeProvider(), {})
    r.tiers[Tier.T3] = ["groq:openai/gpt-oss-120b", "t3f"]
    out = await r.complete(req(Tier.T3))
    assert out.model == "t3f" and not out.abstained       # groq model skipped, never silently sent to OpenRouter
