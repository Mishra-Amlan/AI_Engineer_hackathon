from __future__ import annotations
from collections import defaultdict

# $ per 1M tokens (input, output). Conservative placeholders for cheap models; unknown -> DEFAULT.
# Refresh from https://openrouter.ai/models before relying on these.
PRICES: dict[str, tuple[float, float]] = {   # verified against /api/v1/models (scripts/check_models.py)
    "meta-llama/llama-3.2-1b-instruct": (0.027, 0.201),
    "meta-llama/llama-3.2-3b-instruct": (0.051, 0.335),
    "meta-llama/llama-3.1-8b-instruct": (0.020, 0.040),
    "mistralai/mistral-nemo": (0.029, 0.030),
    "mistralai/mistral-small-24b-instruct-2501": (0.050, 0.080),
    "openai/gpt-oss-20b": (0.018, 0.090),
    "anthropic/claude-haiku-5.5": (0.10, 0.50),
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    "openai/gpt-oss-120b": (0.15, 0.60),   # Groq list price (unverified); pessimistic vs OpenRouter
}
DEFAULT_PRICE = (1.0, 2.0)   # pessimistic for unknown models


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    model = model.split(':', 1)[-1]          # strip provider prefix (e.g. 'groq:')
    pi, po = PRICES.get(model, DEFAULT_PRICE)
    return (prompt_tokens * pi + completion_tokens * po) / 1_000_000


class BudgetTracker:
    def __init__(self, global_daily: float, per_tenant_daily: float):
        self.global_limit, self.tenant_limit = global_daily, per_tenant_daily
        self.global_spent = 0.0
        self.tenant_spent: dict[str, float] = defaultdict(float)

    def can_spend(self, tenant_id: str, estimate: float) -> tuple[bool, str]:
        if self.global_spent + estimate > self.global_limit: return False, "global_budget"
        if self.tenant_spent[tenant_id] + estimate > self.tenant_limit: return False, "tenant_budget"
        return True, ""

    def record(self, tenant_id: str, amount: float) -> None:
        self.global_spent += amount
        self.tenant_spent[tenant_id] += amount
