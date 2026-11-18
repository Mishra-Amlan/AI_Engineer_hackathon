"""Typed settings loaded from .env / environment. Secrets never appear in repr()."""
from __future__ import annotations
import os
from pathlib import Path
from pydantic import BaseModel, ConfigDict, SecretStr


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.split(" #")[0].strip()
    return out


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    openrouter_api_key: SecretStr
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_t1_primary: str
    model_t1_fallback: str
    model_t2_primary: str
    model_t2_fallback: str
    model_t3_primary: str
    model_t3_fallback: str
    model_verifier: str
    router_max_retries: int = 1
    router_retry_backoff_ms: int = 50
    router_request_timeout_ms: int = 8000
    router_breaker_failure_threshold: int = 2
    router_breaker_cooldown_s: int = 30
    router_escalate_max: int = 1
    daily_budget_usd: float = 2.0
    per_tenant_daily_budget_usd: float = 0.5
    per_request_max_tokens: int = 4000
    max_output_tokens: int = 512
    audit_hash_seed: SecretStr = SecretStr("dev-seed")
    cache_ttl_seconds: int = 300
    cache_ttl_jitter_seconds: int = 45

    @classmethod
    def load(cls, env_path: str | Path = ".env", environ: dict[str, str] | None = None) -> "Settings":
        merged = {**load_env_file(Path(env_path)), **(environ if environ is not None else os.environ)}
        g = lambda k, d=None: merged.get(k.upper(), d)
        def num(k, d, t):
            v = g(k)
            return t(v) if v not in (None, "") else d
        return cls(
            openrouter_api_key=SecretStr(g("OPENROUTER_API_KEY", "") or ""),
            openrouter_base_url=g("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model_t1_primary=g("MODEL_T1_PRIMARY"), model_t1_fallback=g("MODEL_T1_FALLBACK"),
            model_t2_primary=g("MODEL_T2_PRIMARY"), model_t2_fallback=g("MODEL_T2_FALLBACK"),
            model_t3_primary=g("MODEL_T3_PRIMARY"), model_t3_fallback=g("MODEL_T3_FALLBACK"),
            model_verifier=g("MODEL_VERIFIER"),
            router_max_retries=num("ROUTER_MAX_RETRIES", 1, int),
            router_retry_backoff_ms=num("ROUTER_RETRY_BACKOFF_MS", 50, int),
            router_request_timeout_ms=num("ROUTER_REQUEST_TIMEOUT_MS", 8000, int),
            router_breaker_failure_threshold=num("ROUTER_BREAKER_FAILURE_THRESHOLD", 2, int),
            router_breaker_cooldown_s=num("ROUTER_BREAKER_COOLDOWN_S", 30, int),
            router_escalate_max=num("ROUTER_ESCALATE_MAX", 1, int),
            daily_budget_usd=num("DAILY_BUDGET_USD", 2.0, float),
            per_tenant_daily_budget_usd=num("PER_TENANT_DAILY_BUDGET_USD", 0.5, float),
            per_request_max_tokens=num("PER_REQUEST_MAX_TOKENS", 4000, int),
            max_output_tokens=num("MAX_OUTPUT_TOKENS", 512, int),
            audit_hash_seed=SecretStr(g("AUDIT_HASH_SEED", "dev-seed") or "dev-seed"),
            cache_ttl_seconds=num("CACHE_TTL_SECONDS", 300, int),
            cache_ttl_jitter_seconds=num("CACHE_TTL_JITTER_SECONDS", 45, int),
        )
