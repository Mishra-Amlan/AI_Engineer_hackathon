# graphify_vault

- Feature: Token savings
- Status: **implemented**
- Implementation: `assistant/graphify.py + mcp_servers/graphify_server.py`
- Model tier: deterministic
- Tool allowlist: ['graph_subgraph']

## Purpose
Depth<=2 pruned context from Obsidian notes.

## Non-goals / guardrails
Read-only; depth hard-capped at 2.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
