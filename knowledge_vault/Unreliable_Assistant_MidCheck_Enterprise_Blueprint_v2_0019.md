---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0019
domain: engineering
risk_tier: 1
version: v1
---
# Gate 10 & Gate 11: Observability, Troubleshooting & Incident Response

Incident Scenario: Hallucination Surge; Automated Alert Trigger: RAGAS Faithfulness < 0.90 (5m window); Immediate Mitigation & Runbook Execution: Raise Cross-Encoder cutoff from 0.42 to 0.55; enforce strict extractive quote mode. Incident Scenario: MCP Server Hang; Automated Alert Trigger: JSON-RPC timeout > 150 ms (> 1% rate); Immediate Mitigation & Runbook Execution: Trip MCP bulkhead circuit, failover to cached read-replica index, restart MCP worker. Incident Scenario: Cache Stampede / Leak; Automated Alert Trigger: Tenant key collision or Redis CPU > 85%; Immediate Mitigation & Runbook Execution: Enforce `SHA256(tenant_id:user_id:norm_query)` prefix + jittered TTL (300s +/- 45s).

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0018]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0020]]
- [[Post_Hardening_Engineering_Audit_Report_0005]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0032]]
