# guardrails

- Feature: Safety (PII + injection)
- Status: **implemented**
- Implementation: `assistant/plugins/`
- Model tier: deterministic
- Tool allowlist: none

## Purpose
Redact PII and block prompt injection before anything is logged, cached or sent to a model.

## Non-goals / guardrails
Fail-closed; cannot be disabled by flags.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
