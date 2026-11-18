---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0030
domain: engineering
risk_tier: 1
version: v1
---
# Gate 13 & Gate 14: Governance, Security-in-Build & Red Teaming

Step 13 — Governance & Security-in-Build: Enforce SHA-256 hash-chained immutable audit logs (`prev_hash + event_payload`), strict tenant isolation (`tenant_id` in every SQLite/Postgres query and Redis key), zero raw PII persistence, and signed MCP server manifests. Step 14 — Red Teaming Suite: Run an automated 100-prompt adversarial red-team suite covering: (1) Direct jailbreaks & system prompt extraction, (2) Indirect prompt injection hidden inside retrieved Obsidian/PDF chunks, (3) Multi-turn crescendo social engineering, (4) Unicode homoglyph & `name[at]domain` PII smuggling, and (5) Tool argument overflow / SQLi fuzzing.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0029]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0031]]
