"""Load-test server. STUB mode: real API + real pre-hooks (PII/injection) + tenant-isolated cache, with a SIMULATED model
latency (env STUB_MODEL_MS) so we can measure the serving layer without paying for / waiting on remote LLM calls."""
import asyncio
import os
import random
from .api import create_app
from .orchestrator import Response
from .plugins.base import PluginManager, RequestContext, Stage
from .plugins.injection import InjectionShield
from .plugins.pii import PiiRedactor
from .tenancy import exact_cache_key


class StubOrchestrator:
    def __init__(self):
        self.plugins = PluginManager([PiiRedactor(), InjectionShield()])
        self.cache: dict[str, dict] = {}
        self.model_ms = float(os.getenv("STUB_MODEL_MS", "40"))
        self.hit_target = float(os.getenv("STUB_CACHE_HIT", "0.4"))

    async def handle(self, tenant_id, user_id, text, session="s"):
        ctx = self.plugins.run_stage(Stage.PRE_EXECUTION, RequestContext(tenant_id, user_id, text))
        if ctx.blocked:
            return Response("I can't help with that request.", "BLOCKED", "r", blocked=True)
        key = exact_cache_key(tenant_id, "shared", ctx.text)
        if key in self.cache:
            return Response(self.cache[key]["t"], "HYBRID_RAG", "r", mode="cache_hit")
        await asyncio.sleep(self.model_ms / 1000 * random.uniform(0.7, 1.3))        # simulated retrieval+generation
        ans = f"[{tenant_id}] answer"
        self.cache[key] = {"t": ans}
        return Response(ans, "HYBRID_RAG", "r", mode="generated")


app = create_app(StubOrchestrator(), jwt_secret=os.getenv("API_JWT_SECRET") or None, rate_per_s=float(os.getenv("RATE_PER_TENANT_S", "0")), burst=int(os.getenv("RATE_BURST", "0")))
