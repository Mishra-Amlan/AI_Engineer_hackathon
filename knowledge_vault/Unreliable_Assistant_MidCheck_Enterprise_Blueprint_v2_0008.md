---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0008
domain: engineering
risk_tier: 1
version: v1
---
# Gate 2: Mandatory Pre-Build Artifact — Workflow Image (`workflow_orchestration.png`)

Before writing application logic, generate a high-DPI (300 DPI) diagram `docs/workflow_orchestration.png` via Graphviz (`diagrams` / `graphviz` Python library) and render it in Streamlit Tab 1. The diagram must explicitly show: Ingress & Security Layer: Ingress -> Pre-Execution Plugins (PII Redactor -> Injection Classifier) -> Redis Semantic Cache Check. Triage & Subagent Routing: Triage Agent (`temperature=0.0`, < 30 ms) branching into Direct Response, Retrieval Subagent, Execution Subagent, or Audit Subagent. MCP & 3-Stage RAG Pipeline: MCP JSON-RPC calls to `mcp-hybrid-rag` (BM25 + Bi-Encoder -> RRF -> Cross-Encoder), `mcp-graphify-vault`, and `mcp-state-store`.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0007]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0009]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0000]]
