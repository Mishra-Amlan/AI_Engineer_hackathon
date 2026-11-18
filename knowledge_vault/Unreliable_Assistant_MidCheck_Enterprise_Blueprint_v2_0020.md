---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0020
domain: engineering
risk_tier: 1
version: v1
---
# Gate 12: Reliability & Failure Handling — 36 Stage-Level Enterprise KPIs

To certify the system as enterprise-grade, all 36 KPIs across 6 architectural stages must be continuously measured and passed in CI/CD and Streamlit Tab 5: Stage: 1. Ingress & Triage; KPI Name & Metric Definition: KPI-01: Pre-Hook Guardrail Latency (p95); Target Threshold: <= 15 ms; Measurement Tool: OTel Span `hook.pre` Stage: 1. Ingress & Triage; KPI Name & Metric Definition: KPI-02: PII Redaction Recall (Email/Phone/SSN/Obfuscated); Target Threshold: >= 99.8%; Measurement Tool: Presidio / Regex Audit Stage: 1. Ingress & Triage; KPI Name & Metric Definition: KPI-03: Prompt Injection Block Rate (Direct + Indirect); Target Threshold: >= 99.5%; Measurement Tool: Red Team Benchmark

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0019]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0021]]
