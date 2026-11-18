"""Golden retrieval set v0 (hand-written from the 3 source docs; scale to 250 in slice 7).
rel = list of groups; each group is a list of substrings, ANY of which marks a chunk relevant to that
group. A question is satisfied when every group has a relevant chunk. neg=True => must abstain."""
G = [
 # Factoid (25%)
 ("factoid", "What BM25 k1 and b values are used?", [["k1 = 1.25", "k1=1.25"]]),
 ("factoid", "What is the RRF smoothing constant?", [["smoothing constant k = 60", "RRF k=60"]]),
 ("factoid", "What is the cross-encoder sigmoid threshold for reranking?", [["threshold > 0.42", "threshold &gt; 0.42", "> 0.42"]]),
 ("factoid", "What chunk size and overlap does the bi-encoder use?", [["chunk = 512 tok, overlap = 64"]]),
 ("factoid", "How many concurrent virtual users must the system sustain?", [["50,000"]]),
 ("factoid", "What is the max_iterations limit for the ReAct loop?", [["max_iterations = 5", "max_steps=5"]]),
 ("factoid", "Which license does Phi-4-mini have?", [["Phi-4-mini"]]),
 ("factoid", "What LoRA rank is recommended for QLoRA fine-tuning?", [["r = 64"]]),
 ("factoid", "What is the target p95 latency of the triage classification?", [["KPI-05"]]),
 ("factoid", "What was the baseline hallucination rate?", [["38.6%"]]),
 ("factoid", "What learning rate is recommended for instruction tuning?", [["2e-4"]]),
 ("factoid", "What is the idempotency key format required for tool calls?", [["UUIDv4"]]),
 # Complex reasoning (25%)
 ("reasoning", "Why was single-keyword BM25 retrieval a problem in the baseline system?", [["keyword blindness"]]),
 ("reasoning", "How does the circuit breaker decide to trip and what state does it move to?", [["HALTED_BREAKER"]]),
 ("reasoning", "What should happen when the cross-encoder top score is below the threshold?", [["abstention"]]),
 ("reasoning", "How is tenant isolation enforced in the cache key design?", [["SHA256(tenant_id"]]),
 ("reasoning", "How does the system prevent goal drift during ReAct tool use?", [["GoalAnchorBlock"]]),
 ("reasoning", "What mitigation applies when p95 latency exceeds 550 ms?", [["semantic cache"]]),
 ("reasoning", "Why choose SmolLM2 for compliance-sensitive deployments?", [["transparency", "provenance"]]),
 ("reasoning", "How do tier 3 mutation actions get approved?", [["PENDING_APPROVAL", "HITL"]]),
 # Multi-hop (20%)
 ("multihop", "Which retrieval stage latency budget is largest and what model does it use?", [["Stage 3", "rerank"], ["bge-reranker-v2-m3"]]),
 ("multihop", "How do the Graphify depth limit and the token reduction KPI relate?", [["depth=2", "depth = 2", "2-hop"], ["KPI-26"]]),
 ("multihop", "Which MCP servers can the retrieval subagent use and what is its guardrail?", [["mcp-hybrid-rag"], ["Read-only"]]),
 ("multihop", "What tool does the load test use and what p99 threshold does it enforce?", [["k6"], ["p(99)"]]),
 ("multihop", "Which SLM suits strict JSON output and what hyperparameters fine-tune it?", [["JSON schema"], ["lora_alpha", "alpha = 16", "alpha=16"]]),
 # Summary (15%)
 ("summary", "Summarize the 36 KPI scorecard result for the hardened build.", [["36"]]),
 ("summary", "Summarize the differences between SLMs and LLMs.", [["Parameter Scale", "Small Language Models"]]),
 ("summary", "Summarize the Streamlit workbench tabs.", [["Tab 1", "Streamlit"]]),
 ("summary", "Give an overview of the red teaming suite coverage.", [["red-team", "Red Team"]]),
 # Negative / unanswerable (15%)
 ("negative", "What is the CEO's salary?", None),
 ("negative", "Which cloud region hosts the production Kubernetes cluster?", None),
 ("negative", "What is the recipe for sourdough bread?", None),
 ("negative", "Who won the 2022 football world cup?", None),
 ("negative", "What is the employee vacation policy?", None),
]
