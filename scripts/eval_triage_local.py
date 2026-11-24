import json, sys, time
sys.path.insert(0, ".")
import asyncio
from assistant.agents.local_triage import LocalTriage
from assistant.agents.triage import Route, TriageAgent, rules_classify
from assistant.config import Settings
from assistant.rag.onnx_models import OnnxEmbedder
from assistant.router.providers import OpenRouterProvider
from assistant.router.router import ModelRouter
from tests.test_slice3_triage import LABELED
async def main():
    s = Settings.load(".env", {"DAILY_BUDGET_USD": "0.05", "PER_TENANT_DAILY_BUDGET_USD": "0.05"})
    ag = TriageAgent(ModelRouter(s, OpenRouterProvider(s.openrouter_api_key.get_secret_value(), s.openrouter_base_url)), local=LocalTriage(OnnxEmbedder()))
    ok, lat, src = 0, {"local": [], "llm": []}, {}
    for q, exp in LABELED:
        t = time.perf_counter(); r = await ag.classify("demo", q); ms = (time.perf_counter() - t) * 1000
        ok += r.route == exp; src[r.source] = src.get(r.source, 0) + 1; lat["local" if r.source.startswith("local") else "llm"].append(ms)
        if r.route != exp: print("MISS", q, r.route.value, r.source)
    L = sorted(lat["local"])
    print(json.dumps({"accuracy": f"{ok}/{len(LABELED)}", "sources": src, "local_p95_ms": round(L[int(.95 * len(L)) - 1], 1) if L else None, "local_share": round(len(L) / len(LABELED), 2)}))
asyncio.run(main())
