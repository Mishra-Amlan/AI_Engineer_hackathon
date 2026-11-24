"""Triage Agent: tags (intent, domain, risk_tier, complexity) and picks a route.
SLM (T1, temp 0) proposes; deterministic rules can only RAISE risk or force routes (never lower).
Route is derived in code, never taken from the model. Fallback = rules-only classifier."""
from __future__ import annotations
import re
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict
from ..router.router import ModelRouter
from ..router.types import Message, RouterRequest, Tier


class Route(str, Enum):
    DIRECT_ANSWER = "DIRECT_ANSWER"
    HYBRID_RAG = "HYBRID_RAG"
    TRANSACTION_EXEC = "TRANSACTION_EXEC"
    REJECT_OOS = "REJECT_OOS"


Intent = Literal["smalltalk", "policy_question", "lookup", "transaction", "out_of_scope"]
Domain = Literal["policy", "inventory", "quality", "general"]


class TriageModelOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intent: Intent
    domain: Domain
    risk_tier: Literal[1, 2, 3]
    complexity: Literal["low", "medium", "high"]


class TriageResult(BaseModel):
    intent: str
    domain: str
    risk_tier: int
    complexity: str
    route: Route
    source: Literal["slm", "rules", "slm+rules", "local", "local+rules"]
    model: str | None = None


_MUTATE = re.compile(r"\b(approve|reject|release|transition|move|change|update|set|cancel|delete|remove|submit|create|mark|quarantine|recall|ship)\b", re.I)
_ENTITY = re.compile(r"\b(SKU-?\d+|LOT-?\s?\d+|batch|order|shipment|workflow)\b", re.I)
_LOOKUP = re.compile(r"\b(verify|status|check|lookup|look up|find|how many|quantity|qty|is .{0,20} approved|list)\b", re.I)
_POLICY = re.compile(r"\b(policy|policies|sop|procedure|protocol|guideline|rule|compliance|allowed|requirements?|how (do|should|can) (i|we)|what is the process)\b", re.I)
_SMALL = re.compile(r"^\s*(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening)|bye|who are you|what can you do)\b[\s!.?]*$", re.I)
_OOS = re.compile(r"\b(weather|stock price|bitcoin|recipe|lyrics|poem|joke|movie|football|cricket score|horoscope|write (me )?(a |an )?(story|essay|song)|translate .{0,20} to)\b", re.I)
_HIGH = re.compile(r"\b(compare|across|versus|vs\.?|why did|root cause|trade-?off|analy[sz]e|multiple|all .{0,15} and)\b", re.I)


def rules_classify(q: str) -> TriageModelOut:
    if _SMALL.match(q): return TriageModelOut(intent="smalltalk", domain="general", risk_tier=1, complexity="low")
    has_entity, mutate = bool(_ENTITY.search(q)), bool(_MUTATE.search(q))
    if _OOS.search(q) and not has_entity and not _POLICY.search(q):
        return TriageModelOut(intent="out_of_scope", domain="general", risk_tier=1, complexity="low")
    cx = "high" if _HIGH.search(q) else ("medium" if len(q.split()) > 18 else "low")
    if mutate and has_entity and not re.match(r"^\s*(what|how|why|which|when|where|who|is|are|can|does|do)\b", q, re.I):
        return TriageModelOut(intent="transaction", domain="inventory", risk_tier=3, complexity=cx)
    if _POLICY.search(q): return TriageModelOut(intent="policy_question", domain="policy", risk_tier=1, complexity=cx)
    if has_entity or _LOOKUP.search(q):
        return TriageModelOut(intent="lookup", domain="quality" if re.search(r"safety|batch|lot", q, re.I) else "inventory",
                              risk_tier=1, complexity=cx)
    return TriageModelOut(intent="policy_question", domain="general", risk_tier=1, complexity=cx)  # safe default: grounded RAG


def route_for(m: TriageModelOut) -> Route:
    if m.intent == "out_of_scope": return Route.REJECT_OOS
    if m.intent == "transaction" or m.risk_tier == 3: return Route.TRANSACTION_EXEC
    if m.intent == "smalltalk": return Route.DIRECT_ANSWER
    return Route.HYBRID_RAG


SYSTEM = """You are a triage classifier for an enterprise assistant whose knowledge base covers: warehouse/quality operations (SKU/LOT/batch), AND engineering and AI-system documentation (RAG, retrieval, agents, LLM/SLM models, fine-tuning, KPIs, load testing, security, observability, architecture). Questions about ANY of these are in scope. Output ONLY JSON:
{"intent": "smalltalk|policy_question|lookup|transaction|out_of_scope",
 "domain": "policy|inventory|quality|general",
 "risk_tier": 1|2|3,
 "complexity": "low|medium|high"}
intent: transaction = the user asks to CHANGE state (approve/release/update/cancel...) -> risk_tier 3.
lookup = read a SKU/LOT/order status -> risk_tier 1. policy_question = SOP/policy/how-to -> 1.
smalltalk = greetings. out_of_scope = clearly unrelated to the knowledge base (weather, jokes, sports, recipes, celebrities, HR/salary gossip, general trivia). If unsure, choose policy_question (never out_of_scope).
Examples:
"Approve the release of LOT-12345" -> {"intent":"transaction","domain":"quality","risk_tier":3,"complexity":"low"}
"What is the return policy?" -> {"intent":"policy_question","domain":"policy","risk_tier":1,"complexity":"low"}
"Is SKU-099 in stock?" -> {"intent":"lookup","domain":"inventory","risk_tier":1,"complexity":"low"}
"hello" -> {"intent":"smalltalk","domain":"general","risk_tier":1,"complexity":"low"}
"what's the weather" -> {"intent":"out_of_scope","domain":"general","risk_tier":1,"complexity":"low"}
"Which license does Phi-4-mini have?" -> {"intent":"policy_question","domain":"general","risk_tier":1,"complexity":"low"}
"What is the max iteration limit of the ReAct loop?" -> {"intent":"policy_question","domain":"general","risk_tier":1,"complexity":"low"}"""


class TriageAgent:
    def __init__(self, router: ModelRouter, use_model: bool = True, local=None, local_threshold: float = 0.85):
        self.router, self.use_model, self.local, self.local_th = router, use_model, local, local_threshold

    async def classify(self, tenant_id: str, text: str, deadline_ms: int = 4000) -> TriageResult:
        rules = rules_classify(text)
        if self.local is not None:                      # cascade: fast local classifier first, LLM only when unsure or disagreeing with rules
            intent, p = self.local.predict(text)
            disagree = (intent == "transaction") != (rules.intent == "transaction") or (intent == "out_of_scope") != (rules.intent == "out_of_scope")
            if p >= self.local_th and not disagree:
                m = TriageModelOut(intent=intent, domain=rules.domain, risk_tier=3 if intent == "transaction" else 1, complexity=rules.complexity)
                return TriageResult(**m.model_dump(), route=route_for(m), source="local", model="local-lr")
        model_out, model_name = None, None
        if self.use_model:
            r = await self.router.complete(RouterRequest(
                tenant_id=tenant_id, tier=Tier.T1, purpose="triage", temperature=0.0, max_tokens=80,
                deadline_ms=deadline_ms, json_schema=TriageModelOut,
                messages=[Message(role="system", content=SYSTEM), Message(role="user", content=text)]))
            if r.parsed and not r.abstained:
                model_out, model_name = TriageModelOut(**r.parsed), r.model
        if model_out is None:
            return TriageResult(**rules.model_dump(), route=route_for(rules), source="rules")
        merged = model_out.model_copy()
        # safety overrides: rules may only raise risk / force mutation routing, never lower it
        if rules.risk_tier > merged.risk_tier or (rules.intent == "transaction" and merged.intent != "transaction"):
            merged = merged.model_copy(update={"risk_tier": max(rules.risk_tier, merged.risk_tier),
                                               "intent": "transaction" if rules.intent == "transaction" else merged.intent})
        if rules.intent == "out_of_scope" and merged.intent == "policy_question":
            merged = merged.model_copy(update={"intent": "out_of_scope"})
        src = "slm+rules" if merged != model_out else "slm"
        return TriageResult(**merged.model_dump(), route=route_for(merged), source=src, model=model_name)
