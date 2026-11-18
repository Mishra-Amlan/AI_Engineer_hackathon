"""RAGAS-lite: LLM-judged proxies for faithfulness / answer relevancy / hallucination, plus context metrics.
NOT the official `ragas` package. Judge is a separate prompt (claim-level) from the runtime verifier."""
from __future__ import annotations
from pydantic import BaseModel
from .agent.generation import split_claims, ungrounded_tokens, sources_block
from .router.router import ModelRouter
from .router.types import Message, RouterRequest, Tier


class Claims(BaseModel):
    supported: list[bool]


class Rel(BaseModel):
    score: float


FAITH = """Judge each numbered claim against the SOURCES. A claim is supported only if a source states it or directly entails it.
Reply ONLY JSON: {"supported":[true,false,...]} with exactly one boolean per claim, in order."""
RELEV = """Rate 0.0-1.0 how directly and completely the ANSWER addresses the QUESTION (ignore whether it is true).
Reply ONLY JSON: {"score": 0.0}"""


async def judge_answer(router: ModelRouter, judge_model: str, q: str, answer: str, chunks: list[dict]) -> dict:
    claims = split_claims(answer)
    f = await router.complete(RouterRequest(tenant_id="eval", tier=Tier.T2, models=[judge_model, "anthropic/claude-haiku-4.5"], json_schema=Claims, max_tokens=400,
        messages=[Message(role="system", content=FAITH), Message(role="user", content=f"SOURCES:\n{sources_block(chunks)}\n\nCLAIMS:\n" +
                  "\n".join(f"{i}. {c}" for i, c in enumerate(claims)))]))
    sup = f.parsed["supported"] if f.parsed else []
    sup = (sup + [False] * len(claims))[:len(claims)] if f.parsed else None
    r = await router.complete(RouterRequest(tenant_id="eval", tier=Tier.T2, models=[judge_model, "anthropic/claude-haiku-4.5"], json_schema=Rel, max_tokens=200,
        messages=[Message(role="system", content=RELEV), Message(role="user", content=f"QUESTION: {q}\nANSWER: {answer}")]))
    return {"f_reason": f.reason if not f.parsed else "", "r_reason": r.reason if not r.parsed else "", "claims": len(claims), "supported": sum(sup) if sup is not None else None,
            "relevancy": r.parsed["score"] if r.parsed else None,
            "ungrounded": ungrounded_tokens(answer, [c["text"] for c in chunks])}
