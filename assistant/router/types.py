from __future__ import annotations
from enum import IntEnum
from pydantic import BaseModel, ConfigDict, Field


class Tier(IntEnum):
    T0 = 0   # deterministic, no model
    T1 = 1   # small / cheap
    T2 = 2   # default generation
    T3 = 3   # complex reasoning


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    content: str


class RouterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str
    tier: Tier = Tier.T2
    messages: list[Message]
    json_schema: type[BaseModel] | None = None      # validate output against this model
    max_tokens: int = 512
    temperature: float = 0.0
    deadline_ms: int = 8000
    extractive_fallback: str | None = None          # grounded text used before abstaining
    escalations: int = 0
    models: list[str] | None = None                 # explicit model list (e.g. independent verifier); replaces the tier ladder
    purpose: str = "generic"                        # e.g. "triage", "generate", "verify"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ProviderResult(BaseModel):
    text: str
    usage: Usage = Usage()
    model: str = ""


class RouterResponse(BaseModel):
    text: str
    parsed: dict | None = None
    model: str | None = None
    tier_requested: Tier
    tier_used: Tier | None = None
    fallback_depth: int = 0
    attempts: int = 0
    degraded: bool = False
    abstained: bool = False
    reason: str = ""
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    trace: list[dict] = Field(default_factory=list)   # router_decision span attrs


ABSTAIN_TEXT = "I can't answer that reliably right now. Please rephrase or try again shortly."


class ProviderError(Exception):
    """kind: rate_limit | timeout | server | bad_output | model_unavailable | auth | budget"""
    RETRYABLE = {"rate_limit", "timeout", "server", "bad_output"}
    FATAL = {"auth", "budget"}

    def __init__(self, kind: str, message: str = ""):
        super().__init__(f"{kind}: {message}")
        self.kind = kind

    @property
    def retryable(self) -> bool:
        return self.kind in self.RETRYABLE

    @property
    def fatal(self) -> bool:
        return self.kind in self.FATAL
