"""Hosted LLM listwise reranker (no local hardware needed). Quality tier: ~1 s per query via the Model Router.
Drop-in for CrossEncoder.predict: returns pre-sigmoid scores so the existing 0.42 threshold / rescue logic applies."""
from __future__ import annotations
import asyncio
import threading
from pydantic import BaseModel
from ..router.router import ModelRouter
from ..router.types import Message, RouterRequest, Tier


_BG: dict = {}


def background_loop() -> asyncio.AbstractEventLoop:
    """One persistent loop thread so pooled HTTP connections never outlive their event loop."""
    if "loop" not in _BG:
        loop = asyncio.new_event_loop(); threading.Thread(target=loop.run_forever, daemon=True).start(); _BG["loop"] = loop
    return _BG["loop"]


class Scores(BaseModel):
    scores: list[float]


SYS = """You are a relevance judge for a retrieval system. Given a QUESTION and numbered PASSAGES, score each passage 0-10:
10 = directly answers the question, 7 = contains key facts needed, 4 = related but not sufficient, 0 = unrelated.
Reply ONLY JSON: {"scores": [..one number per passage, in order..]}"""


class LLMReranker:
    def __init__(self, router: ModelRouter, loop: asyncio.AbstractEventLoop | None = None, tenant_id: str = "rerank",
                 models: list[str] | None = None, max_chars: int = 450, pool: int = 12):
        self.router, self.loop, self.tenant, self.models, self.max_chars, self.pool = router, loop, tenant_id, models, max_chars, pool

    @staticmethod
    def to_logit(s: float) -> float: return (min(10.0, max(0.0, s)) - 3.5) * 0.8

    def predict(self, pairs, batch_size=32):
        if not pairs: return []
        q = pairs[0][0]; docs = [d for _, d in pairs]
        head = docs[: self.pool]                       # only the top of the RRF pool is judged; the rest keep a floor score
        body = "\n".join(f"[{i}] {d[: self.max_chars]}" for i, d in enumerate(head, 1))
        req = RouterRequest(tenant_id=self.tenant, tier=Tier.T2, models=self.models, json_schema=Scores, temperature=0.0, max_tokens=200,
                            purpose="rerank", messages=[Message(role="system", content=SYS), Message(role="user", content=f"QUESTION: {q}\n\nPASSAGES:\n{body}")])
        coro = self.router.complete(req)
        r = asyncio.run_coroutine_threadsafe(coro, self.loop or background_loop()).result(45)
        if r.abstained or not r.parsed or len(r.parsed["scores"]) != len(head):
            raise RuntimeError("llm rerank unavailable")   # retriever degrades to abstain (never ungrounded)
        return [self.to_logit(s) for s in r.parsed["scores"]] + [self.to_logit(0)] * (len(docs) - len(head))
