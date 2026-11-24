# execution

- Feature: Transactions
- Status: **implemented**
- Implementation: `assistant/agent/subagents.py`
- Model tier: T2 reasoner
- Tool allowlist: ['lookup_sku', 'lookup_lot', 'transition_workflow']

## Purpose
Bounded ReAct over state-store tools; Tier-3 requests freeze for human approval.

## Non-goals / guardrails
No RAG/web; never applies Tier-3 itself.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
