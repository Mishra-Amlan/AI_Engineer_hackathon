# eval

- Feature: Evaluation
- Status: **implemented**
- Implementation: `assistant/eval_ragas.py + scripts/eval_ragas.py`
- Model tier: offline T2
- Tool allowlist: none

## Purpose
RAGAS-lite proxy metrics on the golden set.

## Non-goals / guardrails
Never in the request path; proxy judge is not the official ragas package.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
