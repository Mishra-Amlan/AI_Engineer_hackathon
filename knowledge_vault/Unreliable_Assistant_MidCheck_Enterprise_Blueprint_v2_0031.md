---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0031
domain: engineering
risk_tier: 1
version: v1
---
# Gate 15 & Gate 16: Scalability & 50,000-User Load Testing (k6 + JMeter)

To hit 200–600 ms end-to-end latency at 50,000 concurrent virtual users (VUs), deploy horizontally scaled stateless FastAPI workers behind NGINX/Envoy, Redis Cluster for semantic caching, ONNX-quantized Bi-Encoder/Cross-Encoder workers with dynamic micro-batching (batch=32, max_wait=8 ms), and vLLM/TensorRT-LLM with continuous batching and prefix caching.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0030]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0032]]
