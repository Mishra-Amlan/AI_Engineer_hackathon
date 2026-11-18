# CLAUDE.md — "The Unreliable Assistant" → Enterprise-Grade Agentic System

Guidance for Claude Code when working in this repo. Derived from three source docs in this directory:

| Doc | Role |
|---|---|
| `Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2.docx` | **Authoritative spec** (18 gates, 36 KPIs). Build against this. |
| `Post_Hardening_Engineering_Audit_Report.docx` | Claimed post-build results + root-cause baseline. Treat as *targets/evidence to reproduce*, not as verified facts. |
| `SLM_Comprehensive_Guide.docx` | Reference for small-model selection and QLoRA fine-tuning (candidate for Triage / Verification models). |

Status: slices 0–13 implemented to the extent recorded in `design.md` §9 and `evidence/`; run `python3 scripts/gate_report.py` for the computed scorecard. Remaining gaps: 50K/JMeter/soak load, real Redis/Postgres/OTel, local SLM for latency KPIs, quality gates in RAGAS.

## 0. Hard Rules (read first)

1. **No application code before `design.md` (Gate 1) and `docs/workflow_orchestration.png` (Gate 2) exist.** `design.md` goes in repo root and must have 7 sections: charter/boundaries, MCP tool & data contracts, topology/data flow, latency budget, 36-KPI gate matrix, 12-row FMEA, ADRs (hybrid weights, ONNX quantization, Redis key isolation, bounded ReAct).
2. **Tenant isolation everywhere**: `tenant_id` in every Postgres/SQLite query and every Redis key. Cache key = `SHA256(tenant_id:user_id:norm_query)`, TTL 300s ± 45s jitter. Never use global cache keys (the original cross-tenant leak).
3. **Zero raw PII persisted.** PII redaction runs *before* anything is logged, cached or sent to an LLM, and fails closed.
4. **Tier 3 (mutating) actions always require HITL approval.** No autonomous clinical/financial/legal execution.
5. **ReAct loops are bounded and deterministic.** No unbounded retries; no recursive self-calls without state mutation.
6. **Abstain rather than hallucinate** when retrieval confidence is low.
7. Don't claim a KPI passes without a reproducible measurement (OTel span, k6/JMeter output, RAGAS run, red-team log).
8. **Build one slice → test → pass gates → only then the next** (§13). Never batch features.
9. **Every model call goes through the Model Router** with a fallback ladder ending in abstention, never an ungrounded answer (§9).
10. **Every behavior change is versioned, flag-gated and rollback-able** (§10).
11. Each feature has its own scoped agent/component with a contract (§12). Design for millions of users, not just 50K (§11).

## 1. Problem Being Solved (baseline failures)

- Retrieval: single-keyword BM25, chunk fragmentation → 38.6% hallucination.
- Concurrency: sync DB calls, unbatched embeddings, global Redis keys → cross-user leaks, p99 7,100 ms, crash at 120 VUs.
- Control plane: unbounded ReAct + brittle schemas → infinite loops on typos (`SKU99` vs `SKU-099`).
- Tokens: raw policy PDFs dumped into prompts (2,850 tok / 1K queries, $3.40).
- Governance: indirect prompt injection, obfuscated PII (`name[at]domain`), no HITL.

## 2. Target Architecture

**Stack (Gate 0):** Python 3.11, FastAPI + Uvicorn (async), MCP over JSON-RPC 2.0 (stdio for local, Streamable HTTP/SSE for distributed), Pluggy plugin registry, PostgreSQL + pgvector, Redis Cluster, ONNX Runtime, OpenTelemetry → Prometheus/Tempo/Grafana, Streamlit workbench, `uv` for running servers.

**MCP servers** (`mcp_config.json`):
- `hybrid-rag` — `mcp_servers/rag_server.py`, stdio, timeout 150 ms. Exposes `rag://chunks/{id}` resource + `hybrid_retrieve` tool.
- `state-store` — `http://localhost:8081/mcp`, streamable-http, pool 200. Postgres audit + tenant-isolated Redis.
- `graphify-vault` — `mcp_servers/graphify_server.py`, stdio. Obsidian/Graphify subgraph retrieval.

**Lifecycle plugins** (priority order within stage):
- `PRE_EXECUTION`: `pii_redactor` (10, fail_closed), `injection_shield` (20, fail_closed)
- `TOOL_DISPATCH`: `circuit_breaker` (10, max_identical_calls=2)
- `POST_EXECUTION`: `ragas_auditor` (10, min_faithfulness 0.92)
- `ALL_SPANS`: `otel_exporter` → `http://localhost:4317`

**Request flow:** Ingress → PII redact → injection classify → semantic cache → Triage → (Direct | Retrieval | Execution | Audit subagent) → bounded ReAct → circuit breaker → Tier 3 HITL → RAGAS + OTel.

### 3-Stage Hybrid RAG (Gate 3/8) — in `mcp_servers/rag_server.py`

| Stage | Engine | Params | Budget |
|---|---|---|---|
| 1 Sparse | BM25Okapi + Porter stemmer, inverted index | k1=1.25, b=0.75, top_k=50 | <12 ms |
| 2 Dense | `bge-large-en-v1.5` ONNX + FAISS HNSW | chunk 512 tok, overlap 64, efSearch=64, top_k=50 | <25 ms |
| Fusion | RRF | k=60, dedup by `chunk_hash`, pool=40 | <3 ms |
| 3 Rerank | `bge-reranker-v2-m3` ONNX FP16, batch 32 | rerank_k=4, sigmoid threshold >0.42, max_len 512 | <45 ms |

**Abstention short-circuit:** top cross-encoder score < 0.42 → skip LLM, return deterministic abstention in <90 ms.

### Agent control plane (Gates 4–7, 9)
- **ToolExecutionHarness** on every tool call: (1) Pydantic v2 strict validation → (2) deterministic regex auto-repair (`SKU99`→`SKU-099`, `lot 44`→`LOT-00044`) → (3) RBAC tier check (`TIER_1_READ`, `TIER_2_COMPUTE`, `TIER_3_MUTATE`) → (4) UUIDv4 idempotency.
- **State machine:** `INIT → TRIAGE → REASONING → TOOL_CALL → OBSERVATION → VERIFY → DONE/HALTED`. Limits: `max_iterations=5`, `per_step_timeout=120 ms`, `total_loop_budget=450 ms`.
- **Context-drift controls:** immutable `GoalAnchorBlock` at index 0 of every prompt (intent, normalized entity IDs, policy constraints); observations compressed to ≤180 tokens; sliding window of last 3 turns in hot memory, verified facts in Postgres `session_facts` keyed by `session_id`.
- **Triage agent:** temp 0.0, ≤25 ms, emits `(intent, domain, risk_tier, complexity)` → `DIRECT_ANSWER | HYBRID_RAG | TRANSACTION_EXEC | REJECT_OOS`.
- **Subagents (isolation rules):**
  - Retrieval — `hybrid-rag` + `graphify-vault`; **read-only**, cannot call mutating tools.
  - Execution — `state-store` only; **no RAG/web**; Tier 3 triggers HITL freeze.
  - Verification — `state-store` (audit log only); independent context; claim-to-chunk NLI; **can veto** ungrounded drafts.
- **Reliability patterns:** idempotent circuit breaker (`(tool_name, canonical_args_hash)` fails ≥2 → `HALTED_BREAKER` + user remediation prompt); bulkheads (`rag_pool=64`, `db_pool=128`, `llm_pool=256`); async HITL (write `PENDING_APPROVAL` to Postgres, pause until approved).

### Token optimization (Gate 17)
- Policies/SOPs/catalogs → atomic Markdown notes in `knowledge_vault/` with YAML frontmatter (`id`, `domain`, `risk_tier`, `version`) and `[[wikilinks]]`.
- `graphify build ./src ./knowledge_vault --output graph.json`; at runtime traverse **depth ≤ 2** from the query anchor node (~320 tokens vs ~1,400 raw).

### Governance & red team (Gates 13–14)
- SHA-256 hash-chained immutable audit log (`prev_hash + event_payload`); signed MCP server manifests.
- 100-prompt red-team suite: direct jailbreak/system-prompt extraction; indirect injection inside retrieved chunks; multi-turn crescendo; Unicode homoglyph and `name[at]domain` PII smuggling; tool-arg overflow/SQLi fuzzing.

## 3. Deliverables / Repo Layout (expected)

```
design.md                       # Gate 1 (hard gate)
docs/workflow_orchestration.png # Gate 2, 300 DPI, Graphviz, shown in Streamlit Tab 1
mcp_config.json
mcp_servers/{rag_server.py,graphify_server.py,...}
knowledge_vault/                # atomic Obsidian notes
load_tests/{k6_50k_load.js,jmeter_50k_plan.jmx}
app.py                          # Streamlit 6-tab workbench (Gate 18)
```

Streamlit tabs: (1) Architecture & Workflow + HITL queue, (2) Hybrid RAG Lab with k1/b/RRF-k/threshold sliders, (3) MCP & Plugin Inspector with hot toggles, (4) Memory & Graphify Tokens, (5) Red Team & Circuit Breaker, (6) 36-KPI Scorecard & 50K load.

## 4. Latency Budget (p95 ≤ 450 ms, p99 ≤ 600 ms at 50K VUs)

Per-hop budgets: pre-hook ≤15 · triage ≤25 · BM25 ≤12 · dense ≤25 · RRF ≤3 · rerank ≤45 · MCP serialization ≤4 · TTFT p95 ≤180. Scale: stateless FastAPI behind NGINX/Envoy, Redis Cluster, ONNX micro-batching (batch=32, max_wait=8 ms), vLLM/TensorRT-LLM with continuous batching + prefix caching.

## 5. The 36 KPIs (release gates, CI + Streamlit Tab 6)

**Ingress/Triage:** 01 pre-hook p95 ≤15 ms · 02 PII recall ≥99.8% · 03 injection block ≥99.5% · 04 triage accuracy ≥97% · 05 triage p95 ≤25 ms · 06 false-refusal ≤1%.
**Hybrid retrieval:** 07 BM25 ≤12 ms · 08 dense ≤25 ms · 09 rerank ≤45 ms · 10 Recall@50 ≥0.92 · 11 Precision@4 ≥0.88 · 12 MRR@4 ≥0.85 · 13 nDCG@4 ≥0.86.
**Agent/loop:** 14 first-pass schema validity ≥96% · 15 auto-repair ≥90% · 16 loop escape 100% · 17 mean steps ≤2.2 · 18 drift cosine ≥0.85 · 19 HITL enforcement 100%.
**Generation/RAGAS:** 20 faithfulness ≥0.92 · 21 answer relevancy ≥0.90 · 22 entity recall ≥0.85 · 23 abstention accuracy ≥98% · 24 hallucination ≤0.5% · 25 TTFT p95 ≤180 ms.
**Token/Graphify:** 26 token reduction ≥45% · 27 cache hit ≥35% · 28 cross-tenant leaks = 0 · 29 cost ≤$0.45/1K queries · 30 MCP overhead ≤4 ms.
**Scale (50K VUs):** 31 p50 ≤240 ms · 32 p95 ≤450 ms · 33 p99 ≤590 ms · 34 5xx ≤0.05% · 35 ≥8,500 RPS · 36 RSS growth ≤3% over 1-hr soak.

**RAGAS golden set:** 250 questions — Factoid 25%, Complex reasoning 25%, Multi-hop 20%, Summary 15%, Negative/unanswerable 15%. Gates: faithfulness ≥0.92, answer relevancy ≥0.90, context precision ≥0.88, context recall ≥0.85, entity recall ≥0.85.

## 6. Load Testing
- **k6** (`load_tests/k6_50k_load.js`): ramp 0→10K (2m) →50K (3m), hold 5m, down 2m. Thresholds p50<250, p95<450, p99<600, fail rate <0.0005, checks >0.999. Payload uses `tenant_${vu % 50}` and checks response `tenant_id` matches (leak probe). Endpoint `POST /api/v1/agent/query`.
- **JMeter** (`load_tests/jmeter_50k_plan.jmx`): 1 controller + 10 workers × 5,000 threads, ramp 180s, 600s duration, non-GUI. Assertions: duration 600 ms, JSONPath `$.faithfulness >= 0.92`, constant throughput timer, backend listener (InfluxDB/Prometheus).

## 7. Observability & Runbooks
Span names (W3C `traceparent`): `hook.pre`, `cache.lookup`, `triage.classify`, `mcp.rag.bm25`, `mcp.rag.biencoder`, `mcp.rag.rrf`, `mcp.rag.rerank`, `agent.react.step`, `llm.generate`, `hook.post.ragas`.

| Incident | Trigger | Mitigation |
|---|---|---|
| Latency breach | p95 >550 ms for 30s | semantic cache cosine ≥0.92; cut BM25/dense top_k 50→25 |
| Hallucination surge | faithfulness <0.90 (5m) | rerank cutoff 0.42→0.55; strict extractive-quote mode |
| MCP hang | JSON-RPC >150 ms on >1% | trip MCP bulkhead; fail over to cached read-replica; restart worker |
| Cache stampede/leak | key collision or Redis CPU >85% | enforce tenant SHA256 prefix + jittered TTL |

## 8. SLM Guide — How It Applies Here
The SLM guide is general reference, but it directly informs the **Triage Agent** (≤25 ms, temp 0.0) and possibly the Verification/NLI model.
- SLM = 0.5–10B params, single GPU (T4/L4/4090) or CPU, TTFT <50 ms, cheap QLoRA tuning. LLM = 70B+.
- Candidates: Qwen2.5-0.5B/1.5B (routing, classification; Apache 2.0), Qwen2.5-3B/7B (JSON-schema compliance, multi-turn agents), Phi-4-mini 3.8B (structured extraction; MIT), Gemma-2-2B (memory-constrained; Gemma terms), Llama-3.2-1B/3B (framework ecosystem; Llama license), SmolLM2 (full data provenance for compliance), DeepSeek-R1-Distill-Qwen-1.5B (compact CoT; MIT). Catalog also lists SmolLM2-135M/360M/1.7B, Gemma-2-9B, Ministral-3B (commercial license — check before use), Phi-3.5-mini, Qwen2.5-7B.
- **Fine-tune recipe (Unsloth + TRL QLoRA):** 4-bit base, `max_seq_length=2048`, r=64, alpha=16, dropout 0, all linear targets (q,k,v,o,gate,up,down), grad checkpointing "unsloth", seed 3407; batch 2 × grad-accum 4, warmup 0.05, 1–3 epochs, lr 2e-4 (instruction tuning) / 2e-5 (continued pretraining), `adamw_8bit`, wd 0.01; ChatML format with `instruction/input/output` JSON schema; concise strictly-formatted targets; save merged 16-bit.
- SLM KPIs: schema compliance ≥99%, task F1/accuracy ≥92%, p95 TTFT ≤45 ms on one L4/T4.
- Caveat: the guide's example script builds a one-row toy dataset and passes `output` as a bare string rather than a list — fix before real use. Also, high LoRA rank r=64 with alpha=16 (scale 0.25) is atypical; validate on a held-out set.

## 9. Model Router & Fallback Chain (NOT in source docs — added requirement)

The blueprint has a fixed Triage → subagent path but no model selection, provider failover, or degradation policy (only an "LLM 429" FMEA row). Add a `ModelRouter` (`router/`) as an MCP-independent, deterministic component (no LLM call, decision ≤5 ms, config-driven via `router/policy.yaml`).

**Tiers**
- **T0 Deterministic** — cache hit, regex auto-repair, abstention, canned responses. No model call.
- **T1 SLM** (self-hosted, §8 guide) — triage, classification, arg extraction, JSON-schema tasks. Qwen2.5-0.5B/1.5B/3B, Phi-4-mini.
- **T2 Mid LLM** — default grounded generation over reranked chunks.
- **T3 Frontier LLM** — complex reasoning, multi-hop, Verification-veto retry only.
- Concrete model IDs/prices live in `router/model_registry.yaml` (pinned versions); never hard-code in agents.

**Routing inputs:** triage tuple `(intent, domain, risk_tier, complexity)`, prompt token count, retrieval confidence, tenant plan/SLA, remaining tenant budget, provider health score, current load.

**Fallback ladder (per request):** primary model → secondary provider (same tier) → self-hosted SLM / lower tier → extractive answer from reranked chunks → deterministic abstention. Never fail open into an ungrounded answer.

**Triggers:** 429/5xx, timeout > per-step budget (120 ms step / 450 ms loop), schema failure after auto-repair, circuit open for model/provider, budget exhausted.

**Rules**
- Max 1 retry with jittered backoff; no retries on Tier 3 mutations unless idempotency key is present.
- Per-model/provider circuit breaker + health score (error rate, p95); half-open probes.
- Escalate up a tier at most once (e.g., Verification veto); downgrade under load or budget pressure.
- Optional hedged request for p99 on T2 reads only.
- Per-tenant token/cost budgets and rate limits enforced in the router.
- Router policy changes ship via shadow → canary (see §10) and are logged with `router_decision` span attributes (chosen tier, reason, fallback depth).
- Bulkhead pools per provider so one degraded provider cannot starve others.

**Router tests:** policy table unit tests; fault-injection (429 storm, timeout, provider down, malformed output) proving the ladder terminates in ≤N hops and within latency budget; cost-downgrade test; no-fail-open test.

## 10. Rollback, Release Safety & Disaster Recovery (NOT in source docs — added requirement)

Everything that can change behavior must be **versioned, flag-gated and reversible**:
- **Versioned artifacts:** prompts, router policy, model registry, triage model, retrieval index, reranker, Pydantic schemas, thresholds (0.42 etc.), plugin config, Obsidian vault. Each has an immutable version ID recorded in every trace.
- **Feature flags / kill switches** per plugin, agent, model, and tool (extends Streamlit Tab 3 hot toggles to a real flag service).
- **Release flow:** build → CI KPI gates → shadow → canary 1% → 5% → 25% → 100%. **Auto-rollback** when guardrail KPIs breach (p95 >550 ms, faithfulness <0.90, 5xx >0.05%, any cross-tenant leak, HITL bypass). Target rollback ≤5 min, no data loss.
- **Index rollout:** build new index in the background, swap via alias, keep previous version warm; rollback = alias flip.
- **DB migrations:** expand → migrate → contract; always backward compatible with N-1 code; no destructive migration in the same release.
- **Tier 3 mutations:** idempotency keys + compensating actions (saga pattern); every mutation records its inverse; rollback of a business action goes through HITL too.
- **Git:** one tag per completed feature slice (`gate-N-done`) so any slice can be reverted independently.
- **DR:** define RPO/RTO in `design.md`; backups + restore drill; region failover drill (see §11). Rollback and restore drills are CI/chaos tests, not just documentation.

## 11. Scaling Beyond 50K to Millions of Users (NOT in source docs — added requirement)

The blueprint certifies 50K concurrent VUs / ≥8,500 RPS. "Millions of users" is a different target and must be **defined first** in `design.md` (registered users vs DAU vs peak concurrent vs peak RPS). Capacity model: `RPS ≈ concurrency / (latency + think_time)`; model it explicitly, including cache hit ratio and LLM-call fraction.

**Architecture changes needed**
- **Compute:** stateless pods on Kubernetes, HPA/KEDA autoscaling on RPS, queue depth and GPU utilization; separate pools for API, MCP/RAG, ONNX rerank/embedding, LLM inference (vLLM/TensorRT-LLM, continuous batching, prefix caching).
- **Multi-region active-active** with geo-routing; tenant→region affinity where data residency demands it; region failover drill.
- **Data:** Redis Cluster sharded by tenant hash with L1 in-process + L2 Redis cache tiers; Postgres via PgBouncer, read replicas, partitioning by `tenant_id` (and time for audit/`session_facts`); audit log shipped to append-only store.
- **Retrieval:** sharded and replicated vector index (FAISS shards or a managed vector DB); BM25 index sharded; index freshness pipeline; per-shard latency budgets with partial-result policy.
- **Overload protection:** admission control, priority queues (Tier 3/HITL > interactive > batch), per-tenant rate limits and quotas, load shedding with deterministic degraded responses (cache/extractive/abstain), backpressure, request deadlines propagated through MCP calls.
- **LLM capacity:** pooled provider quotas, multi-provider routing (§9), cost ceilings; most traffic should resolve at T0/T1 via cache and SLM.
- **Async path** for long or Tier 3 work (queue + status API) so synchronous latency SLA stays intact.
- **Cost model** per 1K queries at each scale step.

**Load-test ladder** (build → test → proceed): 1K → 10K → 50K (spec) → 250K → target. Each rung: ramp, spike, 1-hr soak, chaos (kill pod/Redis/MCP/provider/region). Use a realistic think-time model so VUs map to RPS (see §14). Don't advance a rung until KPIs 31–36 and the scale KPIs below hold.

**Additional scale KPIs (proposed, X-prefixed to avoid clashing with KPI-01..36)**
- X-01 autoscale reaction to 5× spike: SLA restored ≤120 s
- X-02 load-shed correctness: 0 mutations dropped, 100% degraded responses grounded or abstentions
- X-03 region failover RTO ≤ defined target, RPO ≤ defined target
- X-04 rollback time ≤5 min
- X-05 router fallback success ≥99.9% (some answer within SLA when one provider is down)
- X-06 cost per 1K queries at target scale ≤ budget
- X-07 per-tenant noisy-neighbor impact ≤5% p95 degradation

## 12. Agent-per-Feature Model (extends Gate 6/7)

The blueprint defines Triage + 3 subagents. Every feature gets its own **narrowly scoped agent/component** with a written contract. Keep deterministic code wherever possible; use a model only where needed.

| Feature | Agent / Component | Tier | Tools / MCP | Key guardrail |
|---|---|---|---|---|
| Intake routing | **Triage Agent** | T1 SLM, temp 0 | none | ≤25 ms; fallback = rules classifier |
| Model selection | **Model Router** (§9) | deterministic | model registry | no LLM; budget-aware |
| Safety | **Guardrail plugins** (PII, injection) | deterministic + small classifier | none | fail-closed |
| Query understanding | **Query-Rewrite Agent** | T1 | none | no data access |
| Retrieval | **Retrieval Subagent** | T1/T2 | `hybrid-rag`, `graphify-vault` | read-only |
| Transactions | **Execution Subagent** | T1 + schema | `state-store` | Tier 3 → HITL |
| Grounding | **Verification Subagent** | T1/T2 NLI, independent context | `state-store` (audit) | veto power |
| Context/memory | **Memory Agent** (anchor, compression, session facts) | T1/deterministic | `state-store` | ≤180-token observations |
| Token savings | **Graphify/Vault Agent** | deterministic | `graphify-vault` | depth ≤2 |
| Evaluation | **Eval Agent** (RAGAS, golden set, drift) | offline T2 | read-only | never in request path |
| Ops | **Incident Agent** (alert → runbook) | T1 + rules | metrics, flags | proposes; human approves risky actions |
| Release | **Rollout Controller** | deterministic | flag service | auto-rollback on KPI breach |
| Data ingestion | **Ingestion Agent** (chunk, embed, vault notes, index build) | offline | index store | versioned, signed output |

Each agent ships with: `agents/<name>/contract.md` (purpose, non-goals), Pydantic I/O schemas, tool allowlist, model tier + fallback, timeout/budget, FMEA entries, OTel spans, eval set, owner. Register in `agents/registry.yaml`. Agents communicate only via typed messages, never shared mutable state.

(Development-time: optionally mirror this with Claude Code subagents in `.claude/agents/` — builder, test-writer, reviewer — one workstream per slice.)

## 13. Build → Test → Proceed Workflow (MANDATORY)

Build **one feature slice at a time**. Never start slice N+1 until slice N is green.

**Per-slice loop**
1. **Spec:** update the relevant `design.md` section (contracts, budget, KPIs, FMEA rows, flags).
2. **Tests first:** unit tests + contract tests + failure/fault-injection tests for the slice.
3. **Build** the smallest implementation that satisfies them.
4. **Measure:** run the slice's KPIs and capture evidence (OTel spans, RAGAS output, benchmark logs) in `evidence/<slice>/`.
5. **Review:** security (tenant isolation, PII), simplicity, code review.
6. **Gate:** all slice KPIs pass, no regressions in earlier slices → commit, tag `gate-N-done`, only then proceed. If red: fix or stop and report; never skip ahead.

**Slice order (dependency-driven)**
| # | Slice | Proves |
|---|---|---|
| 0 | `design.md` + `workflow_orchestration.png` (Gates 1–2) | reviewed and locked |
| 1 | Skeleton: FastAPI, config, authN/Z, tenant isolation, OTel, audit hash-chain, flag service | KPI-28 basics, tracing |
| 2 | Plugin framework + PII redactor + injection shield | KPI-01/02/03 |
| 3 | LLM provider abstraction + **Model Router + fallback** + Triage Agent | KPI-04/05/06, X-05 |
| 4 | Hybrid RAG (BM25 → dense → RRF → rerank) + abstention | KPI-07–13, 23 |
| 5 | ToolExecutionHarness + bounded loop + circuit breaker + GoalAnchor/memory | KPI-14–18 |
| 6 | Subagents + HITL gate (Tier 3) | KPI-19 |
| 7 | Generation + Verification + RAGAS suite | KPI-20–25 |
| 8 | Obsidian vault + Graphify pruning | KPI-26, 30 |
| 9 | Semantic cache (tenant-isolated) | KPI-27, 28 |
| 10 | Rollback/flags/canary + DR drills | X-04 |
| 11 | Red team suite (100 prompts) | KPI-03, 02, 19 |
| 12 | Streamlit 6-tab workbench | Gate 18 |
| 13 | Load ladder 1K→50K→scale target | KPI-31–36, X-01..07 |

Test pyramid: unit → contract (MCP/JSON-RPC schemas) → integration (docker-compose) → chaos/fault → load → red team. CI runs all gates; KPI regressions block merge.

## 14. Gaps Found in the Source Docs & Added Items Checklist

**Missing from the docs (now planned above or tracked here):**
- [x] Model router, tiered models, provider fallback (§9)
- [x] Rollback, canary, flags, versioned artifacts, DR (§10)
- [x] Million-user scale path, capacity model, load ladder (§11)
- [x] One agent/component per feature with contracts (§12)
- [x] Build-test-proceed process (§13)
- [ ] AuthN/AuthZ (JWT with tenant claims, RBAC mapping to Tier 1/2/3), secrets management
- [ ] Data retention / deletion (GDPR-style), PII-safe audit payloads
- [ ] Rate limiting, quotas, API versioning (`/api/v1`), streaming contract, request deadlines
- [ ] Prompt/model/config registry with version pinning
- [ ] Ingestion pipeline and index freshness
- [ ] Labeled data for Triage SLM (intent set ≥ enough per class), golden-set ownership/refresh, eval-set leakage control
- [ ] CI/CD pipeline, environments (dev/stage/prod), IaC
- [ ] Cost governance dashboards, per-tenant budgets
- [ ] Runbooks + on-call/ownership (the blueprint lists runbooks only for 4 incidents)
- [ ] Define "end-to-end latency" precisely (see §15)

## 15. Known Inconsistencies in the Source Docs (resolve in `design.md` ADRs)

**Additional issues found on re-check:**
- **Semantic cache vs. key hash:** cache key is `SHA256(tenant_id:user_id:norm_query)` (exact match) but the runbook relies on "semantic cache cosine ≥0.92". An exact hash cannot do similarity. Resolve: namespace by `tenant_id` (hashed prefix), then do embedding-similarity lookup within that namespace; decide whether `user_id` is part of the namespace (it limits hit ratio vs. KPI-27 ≥35%).
- **VUs vs. RPS:** 50K VUs with `sleep(1)` and ~0.4 s latency implies ≈35K RPS, but KPI-35 only requires ≥8,500 RPS (and audit reports 9,240). Implies ~5 s think time or a different load model. Define the user model explicitly.
- **Latency budget math:** retrieval hops sum to ≈125 ms (15+25+12+25+3+45) before LLM generation; a 5-step loop at 120 ms/step = 600 ms exceeds the 450 ms loop budget; "end-to-end p95 ≤450 ms" vs "TTFT ≤180 ms" is ambiguous (full response or first token?). Most multi-step LLM answers cannot hit 450 ms full-completion — define as time-to-first-token with streaming, or exclude generation tail.
- **Mean steps vs. max:** KPI-17 mean ≤2.2 steps but budget allows 5×120 ms; consistent only if most requests are single-step.
- **Subagent naming:** Gate 2 diagram lists an "Audit Subagent"; Gate 7 calls it "Verification Subagent". Treat as the same.
- **Audit log vs. zero-PII:** hash chain hashes `event_payload`; payload must be post-redaction.
- **FMEA:** 12 rows required but only four examples named (Redis down, reranker timeout, MCP crash, LLM 429); add router/provider, index, DB, HITL, cache-leak, flag-service, queue rows.

**Earlier findings:
- **Pipeline naming:** called "3-stage" but audit says "4-stage" (BM25, dense, RRF, rerank). Treat as 3 retrieval stages + fusion step.
- **Triage latency:** ≤25 ms (Gate 6, KPI-05, audit) vs <30 ms (Gate 2 diagram text). Use **25 ms**.
- **FAISS index:** `FAISS-IVF-PQ` (Gate 0 table) vs `FAISS HNSW`, efSearch=64 (Gate 3). Use **HNSW** (efSearch only applies to HNSW) unless memory forces IVF-PQ; record an ADR.
- **Token reduction:** 55% (Gate 0) vs 45–65% (Gate 17) vs 52.4% measured vs KPI ≥45%. Gate = **≥45%**.
- **Reranker threshold:** audit text says "3-Stage" yet lists 4 steps; threshold 0.42 appears consistently.
- **RAGAS audit gate:** plugin config only enforces `min_faithfulness`; add answer relevancy/precision/recall checks to match Gate 3/8 release gates.
- **p99:** SLA "<600" vs KPI-33 "≤590". Use **≤590 ms**.
- **Audit target-row mismatch:** audit's RAGAS "target" column lists 0.92/0.88/0.85 for faith/prec/recall, consistent with blueprint; audit does not report answer relevancy.
- **Hallucination:** audit baseline 38.6%; KPI-24 target ≤0.5%, but audit doesn't report a measured value.
- **Audit credibility:** 50K VU results are asserted without raw artifacts. Re-run before reporting.
- **Gate numbering:** doc headings mix "Gate" and "Step" labels (e.g., stray "Step 6", "Step 8", "Step 10" text inline); map consistently.
- **Roadmap (not in scope now):** shadow-traffic A/B for domain LoRA adapters, multi-region replication, TensorRT-LLM.

## 16. Working Conventions
- Pydantic v2 strict models for all tool I/O; regex constraints and explicit error codes in `design.md`.
- Every new component gets: an OTel span, a KPI mapping, a failure mode in the FMEA, and tests.
- Prefer deterministic code (regex, state machines, thresholds) over LLM calls for guardrails, routing and repair.
- Keep plugins hot-swappable and decoupled from LLM reasoning.
- Source `.docx` files are reference material; don't edit them. Ignore the LibreOffice `.~lock.*#` files.
- Untrusted-data hygiene: extract docs into a scratch dir outside the repo; don't run interpreters from inside it.
