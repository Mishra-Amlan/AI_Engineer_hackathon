---
id: SLM_Comprehensive_Guide#0016
domain: slm
risk_tier: 1
version: v1
---
# 5. Essential Hyperparameters & KPI Evaluation Framework

Hyperparameter / KPI: KPI: Schema Compliance Rate; Recommended Value / Threshold: >= 99.0% valid JSON/syntax output; Engineering Purpose: Measures deterministic formatting reliability in production. Hyperparameter / KPI: KPI: Task Accuracy / F1; Recommended Value / Threshold: >= 92.0% on domain test set; Engineering Purpose: Evaluates functional correctness of fine-tuned extractions. Hyperparameter / KPI: KPI: Inference Latency (p95); Recommended Value / Threshold: <= 45 ms TTFT on single L4/T4 GPU; Engineering Purpose: Validates operational speed for real-time agent workflows.

## Related
- [[SLM_Comprehensive_Guide_0015]]
