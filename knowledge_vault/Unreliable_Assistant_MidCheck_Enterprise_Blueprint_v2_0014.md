---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0014
domain: engineering
risk_tier: 1
version: v1
---
# Gate 5: Context Retention & Limiting Context Drift (ReAct Framework)

1. Immutable Goal Anchoring: Prepend an immutable `GoalAnchorBlock` (original user intent, normalized entity IDs, active policy constraints) at index 0 of every ReAct prompt so tool output noise cannot cause goal drift. 2. Observation Compression: Pass every tool response through an extractive compressor stripping boilerplate JSON keys and truncating observations to <= 180 tokens. 3. Sliding Window + Dual Memory: Keep only the last 3 ReAct turns in hot Redis/RAM memory while persisting verified facts in PostgreSQL (`session_facts` table) keyed by `session_id`.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0013]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0015]]
