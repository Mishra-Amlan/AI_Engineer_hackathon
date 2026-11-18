"""Tenant-isolated semantic cache (ADR-005). In-memory reference impl; same contract as the Redis one.
Lookup = exact key, else cosine >= threshold INSIDE the tenant namespace. Single-flight prevents stampedes."""
from __future__ import annotations
import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Awaitable, Callable
import numpy as np
from .tenancy import exact_cache_key, jittered_ttl, normalize_query, tenant_namespace, validate_tenant_id


@dataclass
class Entry:
    key: str
    vec: np.ndarray
    value: dict
    expires: float
    version: str


class SemanticCache:
    def __init__(self, embedder, threshold: float = 0.92, ttl: int = 300, jitter: int = 45, max_per_tenant: int = 2000,
                 clock: Callable[[], float] = time.monotonic, version: str = "v1"):
        self.emb, self.th, self.ttl, self.jit, self.cap, self.clock, self.version = embedder, threshold, ttl, jitter, max_per_tenant, clock, version
        self._ns: dict[str, OrderedDict[str, Entry]] = {}
        self._inflight: dict[str, asyncio.Future] = {}
        self.stats = {"hit_exact": 0, "hit_semantic": 0, "miss": 0}

    def _vec(self, text: str) -> np.ndarray:
        return np.asarray(self.emb.encode([normalize_query(text)], normalize_embeddings=True, convert_to_numpy=True)[0], dtype="float32")

    def bump_version(self, v: str): self.version = v        # index/prompt/policy change => all old entries unreadable (rollback-safe)

    def lookup(self, tenant_id: str, user_id: str, query: str) -> dict | None:
        ns = self._ns.get(tenant_namespace(tenant_id))
        now = self.clock()
        if ns:
            k = exact_cache_key(tenant_id, user_id, query)
            e = ns.get(k)
            if e and e.expires > now and e.version == self.version:
                ns.move_to_end(k); self.stats["hit_exact"] += 1; return e.value
            if ns:
                q = self._vec(query)
                best, bs = None, -1.0
                for e in ns.values():
                    if e.expires <= now or e.version != self.version: continue
                    s = float(q @ e.vec)
                    if s > bs: best, bs = e, s
                if best is not None and bs >= self.th:
                    self.stats["hit_semantic"] += 1; return best.value
        self.stats["miss"] += 1
        return None

    def store(self, tenant_id: str, user_id: str, query: str, value: dict) -> None:
        nsk = tenant_namespace(tenant_id)
        ns = self._ns.setdefault(nsk, OrderedDict())
        k = exact_cache_key(tenant_id, user_id, query)
        ns[k] = Entry(k, self._vec(query), value, self.clock() + jittered_ttl(self.ttl, self.jit), self.version)
        ns.move_to_end(k)
        while len(ns) > self.cap: ns.popitem(last=False)

    async def get_or_compute(self, tenant_id: str, user_id: str, query: str, compute: Callable[[], Awaitable[tuple[dict, bool]]]):
        """compute() -> (value, cacheable). Concurrent identical misses share one computation."""
        hit = self.lookup(tenant_id, user_id, query)
        if hit is not None: return hit, True
        fk = exact_cache_key(tenant_id, user_id, query)
        if fk in self._inflight:
            return await asyncio.shield(self._inflight[fk]), False
        fut = asyncio.get_running_loop().create_future(); self._inflight[fk] = fut
        try:
            value, cacheable = await compute()
            if cacheable: self.store(tenant_id, user_id, query, value)
            fut.set_result(value); return value, False
        except Exception as e:  # noqa: BLE001
            fut.set_exception(e); fut.exception(); raise
        finally:
            self._inflight.pop(fk, None)

    def purge_tenant(self, tenant_id: str): self._ns.pop(tenant_namespace(tenant_id), None)
