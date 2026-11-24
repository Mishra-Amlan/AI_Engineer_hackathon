# memory

- Feature: Context/memory
- Status: **partial**
- Implementation: `assistant/agent/loop.py`
- Model tier: deterministic
- Tool allowlist: none

## Purpose
Goal anchor, observation compression, 3-turn window, verified-fact store.

## Non-goals / guardrails
In-memory only; Postgres session_facts pending.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
