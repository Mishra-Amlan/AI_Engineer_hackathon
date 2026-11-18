---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0010
domain: engineering
risk_tier: 1
version: v1
---
# Gate 3 & Gate 8: 3-Stage Hybrid RAG Pipeline, Reranking & RAGAS Suite

Implement the complete 3-stage retrieval stack inside `mcp_servers/rag_server.py` with strict latency budgets per stage: Stage: Stage 1: Sparse Lexical; Implementation Engine: BM25Okapi + PorterStemmer + Inverted Index; Hyperparameters & Optimization: k1 = 1.25, b = 0.75, top_k = 50, pre-tokenized; Latency Budget: < 12 ms; Output Artifact: 50 lexical candidates + raw BM25 scores Stage: Stage 2: Dense Semantic; Implementation Engine: Bi-Encoder (`bge-large-en-v1.5` ONNX) + FAISS HNSW; Hyperparameters & Optimization: chunk = 512 tok, overlap = 64 tok, efSearch = 64, top_k = 50; Latency Budget: < 25 ms; Output Artifact: 50 semantic candidates + Cosine similarity

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0009]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0011]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0004]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0012]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0018]]
