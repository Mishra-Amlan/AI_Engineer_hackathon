---
id: SLM_Comprehensive_Guide#0015
domain: slm
risk_tier: 1
version: v1
---
# 5. Essential Hyperparameters & KPI Evaluation Framework

Hyperparameter / KPI: Learning Rate (lr); Recommended Value / Threshold: 2e-4 (instruction tuning) / 2e-5 (continued pre-training); Engineering Purpose: Controls gradient step size for adapter weight updates. Hyperparameter / KPI: LoRA Rank (r) & Alpha; Recommended Value / Threshold: r = 64, alpha = 16; Engineering Purpose: Determines capacity and expressiveness of low-rank matrices. Hyperparameter / KPI: Target Linear Modules; Recommended Value / Threshold: All layers (q, k, v, o, gate, up, down); Engineering Purpose: Ensures MLP logic blocks fully absorb domain syntax. Hyperparameter / KPI: Training Epochs; Recommended Value / Threshold: 1 to 3 epochs; Engineering Purpose: Prevents catastrophic forgetting and overfitting on instruction sets.

## Related
- [[SLM_Comprehensive_Guide_0014]]
- [[SLM_Comprehensive_Guide_0016]]
