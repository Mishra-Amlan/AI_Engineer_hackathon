---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0015
domain: engineering
risk_tier: 3
version: v1
---
# Gate 6 & Gate 7: Triage Agents & Specialized Subagent Topology

Ultra-fast distilled classifier (`<= 25 ms` inference, `temperature = 0.0`) that tags incoming queries with `(intent, domain, risk_tier, complexity)` and routes directly to `DIRECT_ANSWER`, `HYBRID_RAG`, `TRANSACTION_EXEC`, or `REJECT_OOS`.Step 6 (Triage Agent): Subagent: Retrieval Subagent; Core Responsibility: Query rewriting, 3-stage Hybrid RAG, citation grounding.; Bound MCP Servers: `mcp-hybrid-rag`, `mcp-graphify-vault`; Isolation & Guardrail Rule: Read-only; cannot invoke state-mutating tools. Subagent: Execution Subagent; Core Responsibility: Schema validation, form submission, workflow transitions.; Bound MCP Servers: `mcp-state-store`; Isolation & Guardrail Rule: No RAG/external web access; Tier 3 triggers HITL freeze.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0014]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0016]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0034]]
