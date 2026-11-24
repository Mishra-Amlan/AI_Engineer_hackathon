# triage

- Feature: Intake routing
- Status: **implemented**
- Implementation: `assistant/agents/triage.py`
- Model tier: T1 (Haiku 5.5; rules fallback)
- Tool allowlist: none

## Purpose
Classify (intent, domain, risk, complexity); route computed in code, rules may only raise risk.

## Non-goals / guardrails
Never executes tools; never lowers risk; route not taken from model output.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
