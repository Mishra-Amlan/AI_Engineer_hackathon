# model_router

- Feature: Model selection
- Status: **implemented**
- Implementation: `assistant/router/router.py`
- Model tier: deterministic
- Tool allowlist: none

## Purpose
Tiered model ladder with retry, fallback, breaker, budgets, abstention.

## Non-goals / guardrails
No LLM in decision path; never returns unvalidated structured output.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
