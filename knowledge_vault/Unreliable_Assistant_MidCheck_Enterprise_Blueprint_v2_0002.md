---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0002
domain: engineering
risk_tier: 1
version: v1
---
# Gate 0: Enterprise Stack, MCP Servers & Plugin Architecture

Layer / Capability: Precision Reranker; Selected Tool / Protocol: ONNX Runtime (`bge-reranker-v2-m3` FP16); MCP Server / Plugin Binding: In-process Triton / ONNX microservice; Architectural Justification: Sub-35 ms cross-encoder inference via INT8/FP16 quantization and dynamic batching. Layer / Capability: State & Session Cache; Selected Tool / Protocol: PostgreSQL (pgvector) + Redis Cluster; MCP Server / Plugin Binding: MCP Server: `mcp-state-store`; Architectural Justification: ACID long-term audit persistence + sub-millisecond tenant-isolated Redis caching.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0001]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0003]]
