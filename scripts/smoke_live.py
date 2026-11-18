"""Live smoke test (costs a few cents). Usage: python scripts/smoke_live.py"""
import asyncio, sys, time
sys.path.insert(0, ".")
from assistant.config import Settings
from assistant.router.providers import OpenRouterProvider
from assistant.router.router import ModelRouter
from assistant.router.types import Message, RouterRequest, Tier
from assistant.agents.triage import TriageAgent
from tests.test_slice3_triage import LABELED

async def main():
    s = Settings.load(".env", {"DAILY_BUDGET_USD": "0.05", "PER_TENANT_DAILY_BUDGET_USD": "0.05"})
    prov = OpenRouterProvider(s.openrouter_api_key.get_secret_value(), s.openrouter_base_url)
    router = ModelRouter(s, prov)
    print("-- per-model direct calls")
    for tier, models in router.tiers.items():
        for m in models:
            t0 = time.perf_counter()
            try:
                r = await prov.complete(m, [Message(role="user", content="Reply with exactly: pong")], 400 if "gpt-oss" in m else 20, 0.0, 30, False)
                print(f"OK  {m:45} {(time.perf_counter()-t0)*1000:6.0f} ms  {r.text.strip()[:30]!r} tok={r.usage.prompt_tokens}/{r.usage.completion_tokens}")
            except Exception as e:
                print(f"ERR {m:45} {e}")
    print("-- router T2 + fallback ladder")
    out = await router.complete(RouterRequest(tenant_id="smoke", tier=Tier.T2, max_tokens=40,
        messages=[Message(role="user", content="Name one SKU format example.")]))
    print(out.model, out.degraded, f"{out.latency_ms:.0f}ms", out.text[:60].replace("\n", " "))
    print("-- triage (live SLM) on labeled set")
    ag = TriageAgent(router); ok = 0; lat = []; src = {}
    for q, exp in LABELED:
        t0 = time.perf_counter(); r = await ag.classify("smoke", q); lat.append((time.perf_counter()-t0)*1000)
        ok += r.route == exp; src[r.source] = src.get(r.source, 0) + 1
        if r.route != exp: print("  MISS:", q, "->", r.route.value, "expected", exp.value)
    lat.sort()
    print(f"accuracy {ok}/{len(LABELED)} = {ok/len(LABELED):.1%}  sources={src}  p50={lat[len(lat)//2]:.0f}ms p95={lat[int(.95*len(lat))]:.0f}ms")
    print(f"spent ${router.budget.global_spent:.5f}")
asyncio.run(main())
