---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0018
domain: engineering
risk_tier: 1
version: v1
---
# Gate 10 & Gate 11: Observability, Troubleshooting & Incident Response

Instrument every hop with W3C TraceContext (`traceparent`) exporting to OpenTelemetry Collector -> Prometheus + Tempo + Grafana: `hook.pre`, `cache.lookup`, `triage.classify`, `mcp.rag.bm25`, `mcp.rag.biencoder`, `mcp.rag.rrf`, `mcp.rag.rerank`, `agent.react.step`, `llm.generate`, and `hook.post.ragas`.Step 10 (OpenTelemetry Full-Trace Instrumentation): Incident Scenario: Latency Breach (> 600 ms); Automated Alert Trigger: p95 e2e latency > 550 ms for 30s; Immediate Mitigation & Runbook Execution: Enable aggressive semantic cache (cosine >= 0.92), drop BM25/Dense `top_k` from 50 to 25.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0017]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0019]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0010]]
