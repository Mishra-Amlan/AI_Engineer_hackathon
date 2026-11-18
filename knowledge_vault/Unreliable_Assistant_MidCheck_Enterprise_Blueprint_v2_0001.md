---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0001
domain: engineering
risk_tier: 1
version: v1
---
# Gate 0: Enterprise Stack, MCP Servers & Plugin Architecture

Standardize all tool integrations through the Model Context Protocol (MCP) over JSON-RPC 2.0 (stdio for local workers, Streamable HTTP/SSE for distributed microservices) and modular lifecycle plugins: Layer / Capability: Agent Runtime & API; Selected Tool / Protocol: Python 3.11 + FastAPI + Uvicorn (async); MCP Server / Plugin Binding: MCP Host Client (`mcp.ClientSession`); Architectural Justification: Non-blocking async I/O capable of sustaining 50,000 concurrent connections. Layer / Capability: Sparse & Dense Retrieval; Selected Tool / Protocol: Rank-BM25 + FAISS-IVF-PQ + BGE-Large; MCP Server / Plugin Binding: MCP Server: `mcp-hybrid-rag` (Resources + Tools); Architectural Justification: Exposes `rag://chunks/{id}` resources and `hybrid_retrieve` tool over JSON-RPC.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0000]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0002]]
