---
id: Post_Hardening_Engineering_Audit_Report#0007
domain: engineering
risk_tier: 1
version: v1
---
# 3. Before-vs.-After Performance & 36-KPI Benchmark Proof

Performance Dimension: RAGAS Triad (Faith/Prec/Recall); Baseline ('Unreliable'): 0.61 / 0.54 / 0.68; Current Build (Hardened): 0.94 / 0.91 / 0.89; Target SLA / Gate: >= 0.92 / >= 0.88 / >= 0.85; Verification Evidence: 250-Query Golden Set Run Performance Dimension: Prompt Token Cost / 1K Queries; Baseline ('Unreliable'): 2,850 tok ($3.40); Current Build (Hardened): 1,320 tok ($0.38); Target SLA / Gate: >= 45% reduction (<= $0.45); Verification Evidence: OTel Token Counter Audit

## Related
- [[Post_Hardening_Engineering_Audit_Report_0006]]
- [[Post_Hardening_Engineering_Audit_Report_0008]]
