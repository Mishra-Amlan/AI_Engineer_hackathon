"""Deterministic Model Router (ADR-007). No LLM call in the decision path.
Ladder: tier models (primary, fallback) -> lower tiers' models -> extractive text -> abstention.
Never fails open into an ungrounded answer."""
from __future__ import annotations
import asyncio
import json
import re
import time
from typing import Callable
from pydantic import ValidationError
from ..config import Settings
from .breaker import CircuitBreaker
from .budget import BudgetTracker, cost_usd
from .providers import Provider
from .types import (ABSTAIN_TEXT, ProviderError, RouterRequest, RouterResponse, Tier)


def parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m: raise
        return json.loads(m.group(0))


class ModelRouter:
    def __init__(self, settings: Settings, provider: Provider, *,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], "asyncio.Future"] = asyncio.sleep):
        self.s, self.provider, self.clock, self.sleep = settings, provider, clock, sleep
        self.tiers: dict[Tier, list[str]] = {
            Tier.T1: [settings.model_t1_primary, settings.model_t1_fallback],
            Tier.T2: [settings.model_t2_primary, settings.model_t2_fallback],
            Tier.T3: [settings.model_t3_primary, settings.model_t3_fallback],
        }
        self.breakers: dict[str, CircuitBreaker] = {}
        self.budget = BudgetTracker(settings.daily_budget_usd, settings.per_tenant_daily_budget_usd)

    def _breaker(self, model: str) -> CircuitBreaker:
        if model not in self.breakers:
            self.breakers[model] = CircuitBreaker(self.s.router_breaker_failure_threshold,
                                                  self.s.router_breaker_cooldown_s, self.clock)
        return self.breakers[model]

    def ladder(self, tier: Tier) -> list[tuple[Tier, str]]:
        out, seen = [], set()
        for t in sorted((x for x in self.tiers if x <= tier), reverse=True):
            for m in self.tiers[t]:
                if m not in seen:
                    seen.add(m); out.append((t, m))
        return out

    def _finish_fallback(self, req, resp, why, t0):
        resp.reason = why
        resp.degraded = True
        if req.extractive_fallback:
            resp.text, resp.reason = req.extractive_fallback, f"extractive:{why}"
        else:
            resp.text, resp.abstained = ABSTAIN_TEXT, True
        resp.latency_ms = (self.clock() - t0) * 1000
        return resp

    async def complete(self, req: RouterRequest) -> RouterResponse:
        t0 = self.clock()
        resp = RouterResponse(text="", tier_requested=req.tier)
        if req.tier == Tier.T0:
            raise ValueError("T0 is deterministic; do not route to a model")
        if req.escalations > self.s.router_escalate_max:
            return self._finish_fallback(req, resp, "escalation_limit", t0)
        tier = Tier(min(Tier.T3, req.tier + req.escalations))
        resp.tier_requested = tier
        max_tokens = min(req.max_tokens, self.s.max_output_tokens, self.s.per_request_max_tokens)
        ladder = [(tier, m) for m in dict.fromkeys(req.models)] if req.models else self.ladder(tier)
        depth = 0
        for t, model in ladder:
            elapsed_ms = (self.clock() - t0) * 1000
            remaining = req.deadline_ms - elapsed_ms
            if remaining <= 0:
                return self._finish_fallback(req, resp, "deadline", t0)
            br = self._breaker(model)
            if not br.allow():
                resp.trace.append({"model": model, "skip": "breaker_open"}); depth += 1; continue
            est = cost_usd(model, sum(len(m.content) for m in req.messages) // 3, max_tokens)
            ok, why = self.budget.can_spend(req.tenant_id, est)
            if not ok:
                resp.trace.append({"model": model, "skip": why}); depth += 1; continue
            for attempt in range(self.s.router_max_retries + 1):
                remaining = req.deadline_ms - (self.clock() - t0) * 1000
                if remaining <= 0:
                    return self._finish_fallback(req, resp, "deadline", t0)
                resp.attempts += 1
                try:
                    r = await asyncio.wait_for(
                        self.provider.complete(model, req.messages, max_tokens, req.temperature,
                                               min(self.s.router_request_timeout_ms, remaining) / 1000,
                                               req.json_schema is not None),
                        timeout=min(self.s.router_request_timeout_ms, remaining) / 1000 + 0.05)
                    parsed = None
                    if req.json_schema is not None:
                        try:
                            parsed = req.json_schema.model_validate(parse_json(r.text)).model_dump()
                        except (ValueError, ValidationError):
                            raise ProviderError("bad_output", "schema")
                    if not r.text.strip():
                        raise ProviderError("bad_output", "empty")
                    c = cost_usd(model, r.usage.prompt_tokens, r.usage.completion_tokens)
                    self.budget.record(req.tenant_id, c)
                    br.success()
                    resp.trace.append({"model": model, "ok": True, "attempt": attempt})
                    resp.text, resp.parsed, resp.model, resp.tier_used = r.text, parsed, model, t
                    resp.fallback_depth, resp.cost_usd = depth, resp.cost_usd + c
                    resp.degraded = t < tier or depth > 0
                    resp.latency_ms = (self.clock() - t0) * 1000
                    return resp
                except asyncio.TimeoutError:
                    e = ProviderError("timeout")
                except ProviderError as pe:
                    e = pe
                br.failure()
                resp.trace.append({"model": model, "error": e.kind, "attempt": attempt})
                if e.fatal:      # auth/credits are per-provider: trip this model, keep walking the ladder
                    br.failures = br.threshold; br.opened_at = self.clock()
                    break
                if not e.retryable:
                    break
                if attempt < self.s.router_max_retries and not br.state == "open":
                    await self.sleep(self.s.router_retry_backoff_ms / 1000)
                else:
                    break
            depth += 1
        return self._finish_fallback(req, resp, "ladder_exhausted", t0)
