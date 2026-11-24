# rollout_controller

- Feature: Release
- Status: **implemented**
- Implementation: `assistant/release.py`
- Model tier: deterministic
- Tool allowlist: none

## Purpose
Canary 1/5/25/100 with auto-rollback on guardrail breach.

## Non-goals / guardrails
In-process; no real flag service yet.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
