---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0011
domain: engineering
risk_tier: 1
version: v1
---
# Gate 3 & Gate 8: 3-Stage Hybrid RAG Pipeline, Reranking & RAGAS Suite

Stage: Rank Fusion; Implementation Engine: Reciprocal Rank Fusion (RRF); Hyperparameters & Optimization: smoothing constant k = 60, dedup by chunk_hash, pool = 40; Latency Budget: < 3 ms; Output Artifact: Top 40 unified, scale-normalized candidates Stage: Stage 3: Cross-Encoder; Implementation Engine: `bge-reranker-v2-m3` (ONNX FP16, batch=32); Hyperparameters & Optimization: rerank_k = 4, sigmoid threshold > 0.42, max_len = 512; Latency Budget: < 45 ms; Output Artifact: Top 4 verified context chunks + confidence

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0010]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0012]]
