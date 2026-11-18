---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0012
domain: engineering
risk_tier: 1
version: v1
---
# Gate 3 & Gate 8: 3-Stage Hybrid RAG Pipeline, Reranking & RAGAS Suite

Execute automated RAGAS scoring over a 250-question Golden Dataset stratified across Factoid (25%), Complex Reasoning (25%), Multi-Hop (20%), Summary (15%), and Negative/Unanswerable (15%) queries. Enforce release gates: Faithfulness >= 0.92, Answer Relevancy >= 0.90, Context Precision >= 0.88, Context Recall >= 0.85, Context Entity Recall >= 0.85.Step 8 (RAGAS Continuous Evaluation):

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0011]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0013]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0010]]
