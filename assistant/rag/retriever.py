"""3-stage hybrid retrieval (ADR-001): BM25 + dense(HNSW) -> RRF -> cross-encoder rerank -> abstain gate.
Per-stage timings recorded for KPI-07/08/09. Index is per-tenant (tenant isolation by construction)."""
from __future__ import annotations
import re
import time
from dataclasses import dataclass, field
import faiss
import numpy as np
from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi
from ..plugins.injection import InjectionShield
from .ingest import Chunk

_ps = PorterStemmer()
_STOP = set("a an the of to in for and or is are was were be been it this that on at by with as from".split())


def tokenize(text: str) -> list[str]:
    return [_ps.stem(t) for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()) if t not in _STOP]


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class RetrievalParams:
    k1: float = 1.25
    b: float = 0.75
    bm25_top_k: int = 50
    dense_top_k: int = 50
    rrf_k: int = 60
    pool: int = 40
    rerank_k: int = 4
    threshold: float = 0.42
    ef_search: int = 64
    max_len: int = 512
    # Agreement rescue: reranker below threshold but BOTH first-stage retrievers confidently agree
    agreement_rescue: bool = True
    rescue_bm25: float = 7.0
    rescue_dense: float = 0.60


@dataclass
class Hit:
    chunk: Chunk
    bm25: float | None = None
    dense: float | None = None
    rrf: float = 0.0
    rerank: float | None = None


@dataclass
class RetrievalResult:
    hits: list[Hit]
    confidence: float
    abstain: bool
    timings_ms: dict[str, float]
    degraded: bool = False
    low_confidence: bool = False   # rescued by retriever agreement: generation must use strict extractive mode
    quarantined: int = 0
    candidates: dict[str, list[str]] = field(default_factory=dict)   # stage -> chunk ids (for IR metrics)


class HybridRetriever:
    def __init__(self, chunks: list[Chunk], embedder, reranker, params: RetrievalParams | None = None,
                 shield: InjectionShield | None = None):
        self.p = params or RetrievalParams()
        self.embedder, self.reranker, self.shield = embedder, reranker, shield or InjectionShield()
        self.tenant_ids = {c.tenant_id for c in chunks}
        # indirect-injection quarantine at index time
        self.quarantined = [c for c in chunks if self.shield.scan_chunk(c.text)]
        qset = {c.id for c in self.quarantined}
        self.chunks = [c for c in chunks if c.id not in qset]
        self.bm25 = BM25Okapi([tokenize(c.text) for c in self.chunks], k1=self.p.k1, b=self.p.b)
        emb = self.embedder.encode([c.text for c in self.chunks], normalize_embeddings=True,
                                   batch_size=32, convert_to_numpy=True).astype("float32")
        self.index = faiss.IndexHNSWFlat(emb.shape[1], 32, faiss.METRIC_INNER_PRODUCT)
        self.index.hnsw.efConstruction = 100
        self.index.add(emb)
        self.index.hnsw.efSearch = self.p.ef_search

    def retrieve(self, tenant_id: str, query: str, params: RetrievalParams | None = None) -> RetrievalResult:
        if tenant_id not in self.tenant_ids:
            raise PermissionError("unknown tenant")      # per-tenant index; never answer from another tenant
        p, T = params or self.p, {}
        # Stage 1 sparse
        t = time.perf_counter()
        sc = self.bm25.get_scores(tokenize(query))
        top = np.argsort(-sc)[:p.bm25_top_k]
        bm = {int(i): float(sc[i]) for i in top if sc[i] > 0}
        T["rag.bm25"] = (time.perf_counter() - t) * 1000
        # Stage 2 dense
        t = time.perf_counter()
        qv = self.embedder.encode([f"Represent this sentence for searching relevant passages: {query}"],
                                  normalize_embeddings=True, convert_to_numpy=True).astype("float32")
        self.index.hnsw.efSearch = p.ef_search
        D, I = self.index.search(qv, min(p.dense_top_k, len(self.chunks)))
        dn = {int(i): float(d) for d, i in zip(D[0], I[0]) if i >= 0}
        T["rag.dense"] = (time.perf_counter() - t) * 1000
        # RRF
        t = time.perf_counter()
        fused: dict[int, Hit] = {}
        for ranking, key in ((list(bm), "bm25"), (list(dn), "dense")):
            for rank, i in enumerate(ranking, 1):
                h = fused.setdefault(i, Hit(self.chunks[i], bm.get(i), dn.get(i)))
                h.rrf += 1.0 / (p.rrf_k + rank)
        seen, pool = set(), []
        for h in sorted(fused.values(), key=lambda h: -h.rrf):
            if h.chunk.chunk_hash in seen: continue
            seen.add(h.chunk.chunk_hash); pool.append(h)
            if len(pool) >= p.pool: break
        T["rag.rrf"] = (time.perf_counter() - t) * 1000
        # Stage 3 rerank (degrade to RRF order if reranker fails)
        t, degraded = time.perf_counter(), False
        try:
            scores = self.reranker.predict([(query, h.chunk.text) for h in pool], batch_size=32)
            for h, s in zip(pool, scores):
                h.rerank = float(sigmoid(float(s)))
            ranked = sorted(pool, key=lambda h: -h.rerank)
            conf = ranked[0].rerank if ranked else 0.0
            abstain = conf < p.threshold
        except Exception:  # noqa: BLE001
            degraded, ranked = True, pool
            conf, abstain = 0.0, True      # no calibrated score => cannot certify grounding => abstain
        T["rag.rerank"] = (time.perf_counter() - t) * 1000
        rescued = False
        if abstain and not degraded and p.agreement_rescue and bm and dn:
            b_ids, d_ids = list(bm), list(dn)
            top_rrf = pool[0] if pool else None
            ci = self.chunks.index(top_rrf.chunk) if top_rrf else None
            if (top_rrf and max(bm.values()) >= p.rescue_bm25 and max(dn.values()) >= p.rescue_dense
                    and ci in b_ids[:3] and ci in d_ids[:3]):
                rescued, abstain, ranked = True, False, pool
        top_hits = [h for h in ranked if (h.rerank or 0) >= p.threshold][:p.rerank_k] if not (degraded or rescued) else ranked[:p.rerank_k]
        return RetrievalResult(hits=[] if abstain else top_hits, confidence=conf, abstain=abstain, timings_ms=T,
                               degraded=degraded, low_confidence=rescued, quarantined=len(self.quarantined),
                               candidates={"bm25": [self.chunks[i].id for i in bm], "dense": [self.chunks[i].id for i in dn],
                                           "fused": [h.chunk.id for h in pool],
                                           "final": [h.chunk.id for h in ranked[:p.rerank_k]]})
