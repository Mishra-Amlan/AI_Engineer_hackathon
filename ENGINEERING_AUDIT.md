# Final engineering audit — The Unreliable Assistant

Generated from evidence in this repo (`evidence/`, `python3 scripts/gate_report.py`). Spec: `Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2.docx` + `design.md`.
Note on the supplied *Post-Hardening Audit Report*: its numbers (50K VUs, p95 390 ms, 36/36 KPIs) are **not reproduced** here; this audit reports only what was measured on a 4-core / 16 GB host.

## 0. Workflow coverage (the 9-step instructions)
| Step | Status | Where / notes |
|---|---|---|
| 1 Plan mode / design.md | ✅ | `design.md` (7 sections, 17 ADRs, slice table), `CLAUDE.md` plan incl. router, fallback, rollback, scale |
| 2 Base application | ✅ | slices 1,2,5 (config, tenancy, audit, plugins, harness, loop); `assistant/main.py` end-to-end app |
| 3 Model Router | ✅ | `assistant/router/`; 25 tests; selection logging added |
| 4 Fallback | ✅ (deviation) | built **together with** the router in one slice rather than separately; tests cover primary ok/fail, fallback ok/fail, loop bound, logging |
| 5 Rollback | ✅ | `assistant/release.py`; 11 tests: upgrade, failed upgrade, auto-rollback on 5 guardrails, restore, cache invalidation. In-process (no file-based config restore) |
| 6 Hardening review | ✅ | `HARDENING_REVIEW.md` (11 fixed, 9 open) |
| 7 Audit evidence | ✅ | this document + `evidence/` |
| 8 Local deployment | ✅ | `requirements.txt`, `README.md`, `.env.example`; app run locally and smoke-tested (§4) |
| 9 GitHub push | ⏳ | committed in `/home/labuser/AI_Engineer_hackthon`; needs your credentials to push |

## 1. Architecture summary
Ingress (FastAPI, tenant header = body = JWT claim, per-tenant rate limit, W3C traceparent) → PII redactor → injection shield (fail-closed) → tenant semantic cache →
triage cascade (local int8-ONNX classifier → LLM → rules) → {canned | retrieval subagent → generation → **independent verifier with quote proof** → extractive fallback | execution subagent (bounded ReAct, tool harness, SKU/LOT state-store) → HITL approval}.
Every model call: Model Router (tiers, retry, fallback, breakers, budgets, abstention). Diagram: `docs/workflow_orchestration.png`.

## 2. Requirements coverage
Implemented: 3-stage hybrid RAG + abstention, MCP servers (hybrid-rag, graphify-vault), plugins, harness + auto-repair, bounded loop + breaker + goal anchor, HITL with separation of duties, verification, Graphify token pruning (−70%), semantic cache, flags/canary/rollback, 100-prompt red team, Streamlit 6-tab workbench, k6/JMeter plans, hash-chained audit.
Not implemented / stand-ins: Redis, Postgres (+pgvector, `session_facts`), OTLP exporter, `mcp-state-store` as a real MCP server, streaming TTFT, Pluggy registry (own plugin manager), bge-large / bge-reranker-v2-m3 (dev models: bge-small, MiniLM-L6 cross-encoder).

## 3. Test scenarios and 4. results
| Area | Result |
|---|---|
| Fast suite | **195 passed** (+6 slow real-model tests: 4 pass, 2 documented xfail history) |
| Red team (100 prompts × 5 categories) | 100% blocked/redacted/rejected (co-developed rules: regression guard) |
| Live pipeline smoke (JWT on) | no token 401; wrong-tenant token 403; SKU lookup 200 from state store; release request → PENDING; non-approver 403; requester-as-approver 409; approver applies once; re-approve 409; cache hit 0.5 ms; injection blocked; OOS canned 30 ms |
| RAGAS-lite (34 q, proxy judge) | faithfulness 0.97 ✅, hallucination 2.6% ❌ (≤0.5%), relevancy 0.65 ❌ (≥0.90), entity recall 0.84 ❌ (≥0.85), abstention 5/5 ✅ |
| Retrieval (dev models) | recall@50 1.00 ✅, MRR@4 0.86 ✅, nDCG@4 0.78 ❌, precision 0.65 ❌ |
| Load (stub model, 4 uvicorn workers, k6 on same host) | 1K/5K/10K/20K VUs PASS (p99 ≤116 ms, 0 errors) at ≤0.8K RPS; 50K aborted (k6 ≈9 GB RSS) |
| KPI matrix | **16 pass / 8 fail / 12 pending** of 36 |

## 5. Issues discovered, 6. fixes applied
See `HARDENING_REVIEW.md` (11 fixed with regression tests; 9 open).

## 7. Remaining risks
In-memory state (restart loses pending approvals and audit); reranker latency vs 45 ms budget; RAGAS quality gaps on a small hand-written set; no real flag service/DR drill; HS256 JWT without rotation; load beyond ~1.4K RPS/host untested; Docker image untested.

## 8. Performance observations
Remote-LLM answer: ~3 s (state lookup) to ~9 s (RAG: triage + generate + verify); p50 8.9 s / p95 17 s in eval. Cache hit 0.5 ms; canned 30 ms. Local triage p95 19.5 ms (62% of queries). Dense query embedding ~10 ms (int8 ONNX). Rerank 330–650 ms/12 pairs, ~1.6–2.5 s/40 pairs on CPU. Token use: context −70% via Graphify; ≈$0.002/question incl. judge in eval ($0.07 per 34 q).

## 9. Reliability assessment
Strong on safety invariants (no mutation without approval — property test over 200 random flows; bounded loops — 60/60 chaos escapes; fail-closed verification/guardrails; ladder always terminates in ≤12 hops with an abstention). Weak on durability (in-memory) and on unmeasured scale.

## 10. Recommended next improvements
1) Postgres+Redis (audit, HITL, cache, sessions). 2) Hosted/GPU reranker (bge-reranker-v2-m3) and re-calibrate threshold. 3) 250-question independent golden set + stronger relevancy handling. 4) Streaming + TTFT measurement. 5) Run 50K/JMeter/soak on a multi-node rig. 6) OTLP export + dashboards. 7) JWKS/IdP, key rotation. 8) Independent red-team set. 9) Build-test the Docker image.
