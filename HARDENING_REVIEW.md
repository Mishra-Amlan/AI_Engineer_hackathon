# Engineering hardening review

Scope: whole application, evaluated on the 14 dimensions below. Every finding lists severity, evidence, root cause, fix and component.
Severity: **Critical** = data leak / unsafe mutation, **High** = wrong or unsafe behaviour under normal use, **Med** = degraded quality/availability, **Low** = hygiene.

## Findings that were found and FIXED (each retested; regression test in `tests/`)
| # | Sev | Finding | Evidence | Root cause | Fix | Component |
|---|---|---|---|---|---|---|
| 1 | High | Router breaker opened on malformed model output, disabling healthy models | RAGAS judge calls returned `ladder_exhausted`; first faithfulness 1.0 was computed on a subset | schema failures counted as provider failures | only transport errors trip the breaker (`test_schema_failures_do_not_open_breaker...`) | router |
| 2 | High | Injection shield quarantined legitimate documents | 3 chunks mentioning `tenant_id` dropped; 2 questions lost their context | tenant-probe rule applied to documents | rule applies to user input only; tenancy is structural (`test_legit_docs_mentioning_tenant_id...`) | plugins |
| 3 | High | Email with apostrophe leaked name fragment | red-team case `jack.o'neil@…` → `jack.o'[EMAIL]` | local-part regex lacked `'` | regex extended | PII redactor |
| 4 | High | Legit technical questions routed to REJECT_OOS | 8/27 answerable questions refused in live eval | triage prompt described only warehouse scope | scope widened + examples; local classifier trained on mixed scope | triage |
| 5 | High | Verifier approved unsupported claims | independent judge: 7.8% claims unsupported ("Stage 2 has the largest budget") | verifier accepted plausible claims | every supported claim needs a literal quote found in sources; deterministic number/ID grounding; hallucination 7.8% → 2.6% | verification |
| 6 | Med | SKU/LOT status questions answered from documents (abstained) | live smoke: "How many units of sku99" → "documents do not contain…" | lookup intent mapped to RAG | lookup + entity id → execution subagent (state-store Tier-1) (`test_sku_lot_lookup_routes...`) | orchestrator |
| 7 | Med | Idle keep-alive resets under load | 14% errors at 5K VUs, `connection reset by peer` | uvicorn default keep-alive 5 s = client think time | `--timeout-keep-alive 75/120`, larger backlog; 0 errors afterwards | deployment |
| 8 | Med | Retrieval killed by the 120 ms tool timeout | live eval: every answerable question abstained | one timeout for all tools | per-tool `timeout_s` override | harness |
| 9 | Med | Unknown-tool probing possible | allowlist checked after tool lookup | check ordering | allowlist first (`E_FORBIDDEN` for any non-listed name) | harness |
| 10 | Low | Shared mutable `_t0` in router (concurrency bug) | found in review | instance attribute used per request | request-local timing; 100-way concurrency test | router |
| 11 | Low | No decision logging | router choices only visible in response trace | — | structured `logging` of route/selection/failure/skip/ladder-end and rollback (`test_router_logs_...`) | router, release |

## Open findings (NOT fixed) — remaining risks
| # | Sev | Finding | Evidence | Why open |
|---|---|---|---|---|
| A | High | Reranker 330–2,500 ms on CPU vs 45 ms budget (KPI-09) | `scripts/bench_onnx.py` | needs GPU/hosted reranker; shrinking pool cost MRR 0.86→0.74; LLM reranker rejected (ADR-017) |
| B | High | Audit log, HITL queue, cache and session memory are in-process | design | no Postgres/Redis provisioned; restart loses pending approvals |
| C | High | RAGAS gates fail: relevancy 0.65/0.90, hallucination 2.6%/0.5%, entity recall 0.84/0.85 | `evidence/slice7/ragas.json` | small hand-written 34-question set; needs larger independent set + stronger reranker |
| D | Med | End-to-end latency 3–9 s with remote LLM; KPI-25 (TTFT) unmeasured, no streaming | live smoke | remote API; streaming not built |
| E | Med | JWT HS256 shared secret, no rotation/JWKS; approver roles from token only | `assistant/api.py` | no IdP available |
| F | Med | Red-team suite co-developed with the rules (100% is a regression guard, not an independent audit) | `redteam/suite.py` | needs independent adversarial set |
| G | Med | 50K/JMeter/1-h soak not run; 10K+ tiers throttled to ~0.7K RPS | `evidence/load/` | host: 4 cores / 16 GB |
| H | Low | Dockerfile/compose written but not build-tested | — | not verified on host |
| I | Low | Cost per 1K queries ≈ $2 in eval (incl. judge) vs $0.45 target; production mix unmeasured | RAGAS runs | needs traffic measurement |

## Review by dimension
1 Reliability — router ladder bounded (≤12 hops), breakers per model, deterministic abstention; chaos loop test 60/60 escapes. 2 Scalability — stateless API, per-tenant limits, cache single-flight; capacity measured only to ~1.4K RPS/host. 3 Error handling — errors hidden from clients (500 generic), typed tool errors. 4 Model routing — tiers + budgets, tested. 5 Fallback — retry once → fallback model → lower tier → extractive → abstain (never ungrounded). 6 Rollback — artifact pointer flip + auto-rollback on 5 guardrails, cache invalidated; in-process only. 7 Security — tenant header/body/token binding, fail-closed guards, tool allowlists, HITL separation of duties. 8 Prompt injection — user input, retrieved chunks (index-time quarantine) and tool outputs scanned; sources delimited as data. 9 Red team — 100 prompts, 5 categories, all handled. 10 Tokens — Graphify cuts context 1,646→494 tokens (−70%, recall 0.90). 11 Latency — see audit report. 12 Observability — structured logs, W3C traceparent, per-hop `spans_ms`, hash-chained audit; no OTLP export. 13 Config — `.env` + typed `Settings`, secrets never in repr, versioned artifacts. 14 Failure recovery — fail-closed verification, HITL retry-safe apply, flag last-known-good.
