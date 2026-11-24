# retrieval

- Feature: Retrieval
- Status: **implemented**
- Implementation: `assistant/agent/subagents.py`
- Model tier: deterministic pipeline
- Tool allowlist: ['hybrid_retrieve']

## Purpose
Hybrid retrieval with abstention and low-confidence flagging.

## Non-goals / guardrails
Read-only; cannot call mutating tools.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
