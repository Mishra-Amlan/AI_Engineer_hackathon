---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0021
domain: engineering
risk_tier: 1
version: v1
---
# Gate 12: Reliability & Failure Handling — 36 Stage-Level Enterprise KPIs

Stage: 1. Ingress & Triage; KPI Name & Metric Definition: KPI-04: Triage Routing Accuracy; Target Threshold: >= 97.0%; Measurement Tool: Labeled Intent Set Stage: 1. Ingress & Triage; KPI Name & Metric Definition: KPI-05: Triage Classification Latency (p95); Target Threshold: <= 25 ms; Measurement Tool: OTel Span `triage` Stage: 1. Ingress & Triage; KPI Name & Metric Definition: KPI-06: False Positive Refusal Rate on Benign Queries; Target Threshold: <= 1.0%; Measurement Tool: Benign Control Set Stage: 2. Hybrid Retrieval; KPI Name & Metric Definition: KPI-07: Stage 1 BM25 Retrieval Latency (p95); Target Threshold: <= 12 ms; Measurement Tool: OTel Span `rag.bm25`

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0020]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0022]]
