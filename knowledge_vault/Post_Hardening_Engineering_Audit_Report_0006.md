---
id: Post_Hardening_Engineering_Audit_Report#0006
domain: engineering
risk_tier: 1
version: v1
---
# 3. Before-vs.-After Performance & 36-KPI Benchmark Proof

The table below documents empirical before-and-after performance metrics across core enterprise dimensions: Performance Dimension: End-to-End Latency (p50/p95/p99); Baseline ('Unreliable'): 2,400 / 4,800 / 7,100 ms; Current Build (Hardened): 185 / 390 / 540 ms; Target SLA / Gate: 200–600 ms (p99 < 600 ms); Verification Evidence: k6 & JMeter 50K VU Summary Performance Dimension: Throughput @ 50,000 VUs; Baseline ('Unreliable'): Crashed at 120 VUs; Current Build (Hardened): 9,240 RPS (0.01% 5xx); Target SLA / Gate: >= 8,500 RPS (5xx < 0.05%); Verification Evidence: Load Test Dashboard

## Related
- [[Post_Hardening_Engineering_Audit_Report_0005]]
- [[Post_Hardening_Engineering_Audit_Report_0007]]
