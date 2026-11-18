---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0017
domain: engineering
risk_tier: 3
version: v1
---
# Gate 9: Enterprise Design Patterns & Reliability Elements

1. Idempotent Circuit Breaker: Trips if `(tool_name, canonical_args_hash)` fails >= 2 times; transitions to `HALTED_BREAKER` and returns a structured user remediation prompt. 2. Bulkhead Isolation: Isolated thread/process pools per MCP server (`rag_pool=64`, `db_pool=128`, `llm_pool=256`) so a slow reranker never starves health checks or triage routing. 3. Deterministic Abstention Short-Circuit: When Cross-Encoder top score < 0.42, bypass LLM generation and emit a deterministic abstention response in < 90 ms (zero hallucination risk + 80% token savings). 4. Asynchronous HITL Gate: Tier 3 mutations write a `PENDING_APPROVAL` record to Postgres and pause execution until an authorized reviewer approves via UI/API.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0016]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0018]]
