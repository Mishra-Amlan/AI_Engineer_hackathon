---
id: SLM_Comprehensive_Guide#0003
domain: slm
risk_tier: 1
version: v1
---
# 1. SLM vs. LLM: Definitive Comparison & Architectural Differences

SLMs do not simply shrink LLM architectures; they incorporate specialized architectural designs to maximize intelligence per parameter: Grouped-Query & Multi-Query Attention: Unlike traditional decoders that store full Key-Value pairs, models like Phi and Qwen leverage Grouped-Query Attention (GQA) and Multi-Query Attention (MQA) to drastically reduce memory bandwidth bottlenecks during long-context inference. Hybrid & State-Space Layers: Many modern SLMs incorporate explicit reasoning mechanisms or hybrid architectures (combining dense transformer blocks with selective state-space layers) to maintain logical consistency across multi-step agent workflows. Quantization-Optimized Topologies: SLMs utilize advanced quantization-aware training (QAT) and packed embeddings, enabling 4-bit and 8-bit quantized weights with virtually zero degradation in perplexity or task accuracy.

## Related
- [[SLM_Comprehensive_Guide_0002]]
- [[SLM_Comprehensive_Guide_0004]]
