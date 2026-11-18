---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0013
domain: engineering
risk_tier: 3
version: v1
---
# Gate 4: Harness Engineering (Tool Routing) & Loop Engineering

Tool Routing Harness: Every MCP tool call passes through `ToolExecutionHarness`: (1) Pydantic v2 strict validation, (2) deterministic regex auto-repair (e.g., `SKU99` -> `SKU-099`, `lot 44` -> `LOT-00044`), (3) RBAC permission tier check (`TIER_1_READ`, `TIER_2_COMPUTE`, `TIER_3_MUTATE`), and (4) `UUIDv4` idempotency enforcement. Bounded Loop Engineering: Enforce a deterministic state machine (`INIT -> TRIAGE -> REASONING -> TOOL_CALL -> OBSERVATION -> VERIFY -> DONE/HALTED`). Hard limits: `max_iterations = 5`, `per_step_timeout = 120 ms`, `total_loop_budget = 450 ms`, and zero recursive self-calls without state mutation.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0012]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0014]]
- [[Post_Hardening_Engineering_Audit_Report_0002]]
