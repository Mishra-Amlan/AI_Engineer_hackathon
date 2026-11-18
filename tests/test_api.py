import httpx
import pytest
from assistant.api import create_app
from assistant.orchestrator import Response

class StubOrch:
    def __init__(self): self.seen = []
    async def handle(self, tenant, user, text, session):
        self.seen.append((tenant, user, text))
        if text == "boom": raise RuntimeError("secret internals")
        return Response(f"echo:{text}", "HYBRID_RAG", "rid", spans_ms={"total": 1.0})

def client(o=None):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(o or StubOrch())), base_url="http://t")

async def test_health_and_query_retains_tenant():
    async with client() as c:
        assert (await c.get("/health")).status_code == 200
        r = await c.post("/api/v1/agent/query", json={"tenant_id": "tenant_7", "user_id": "u", "query": "hi"}, headers={"X-Tenant-ID": "tenant_7"})
        assert r.status_code == 200 and r.json()["tenant_id"] == "tenant_7" and r.json()["answer"] == "echo:hi"

async def test_tenant_header_mismatch_and_missing_rejected_before_processing():
    o = StubOrch()
    async with client(o) as c:
        for h in ({"X-Tenant-ID": "other"}, {}):
            r = await c.post("/api/v1/agent/query", json={"tenant_id": "tenant_7", "user_id": "u", "query": "hi"}, headers=h)
            assert r.status_code == 403
    assert o.seen == []

async def test_validation_and_error_hiding():
    async with client() as c:
        H = {"X-Tenant-ID": "t"}
        assert (await c.post("/api/v1/agent/query", json={"tenant_id": "bad t!", "user_id": "u", "query": "x"}, headers={"X-Tenant-ID": "bad t!"})).status_code == 422
        assert (await c.post("/api/v1/agent/query", json={"tenant_id": "t", "user_id": "u", "query": ""}, headers=H)).status_code == 422
        assert (await c.post("/api/v1/agent/query", json={"tenant_id": "t", "user_id": "u", "query": "x", "evil": 1}, headers=H)).status_code == 422
        r = await c.post("/api/v1/agent/query", json={"tenant_id": "t", "user_id": "u", "query": "boom"}, headers=H)
        assert r.status_code == 500 and "secret" not in r.text

async def test_concurrent_tenants_never_cross():
    import asyncio
    async with client() as c:
        async def one(i):
            t = f"tenant_{i % 50}"
            r = await c.post("/api/v1/agent/query", json={"tenant_id": t, "user_id": f"u{i}", "query": "q"}, headers={"X-Tenant-ID": t})
            return r.json()["tenant_id"] == t
        assert all(await asyncio.gather(*[one(i) for i in range(500)]))
