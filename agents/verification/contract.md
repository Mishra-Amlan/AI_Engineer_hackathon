# verification

- Feature: Grounding
- Status: **implemented**
- Implementation: `assistant/agent/generation.py`
- Model tier: independent model (haiku-4.5)
- Tool allowlist: none

## Purpose
Claim-level fact check with literal-quote proof plus deterministic number/ID grounding; can veto.

## Non-goals / guardrails
Never sees generator prompt; fails closed to extractive answer.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
