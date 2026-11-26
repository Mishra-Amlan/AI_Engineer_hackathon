# The Unreliable Assistant → Enterprise-Grade Agentic System

A tenant-isolated, grounded Q&A + workflow assistant: PII/injection guards → semantic cache → triage (local classifier + LLM) →
hybrid RAG (BM25 + dense + RRF + cross-encoder) → generation with an **independent verifier** → bounded ReAct tool loop → **human approval** for any mutation.
All model calls go through a **Model Router** (tiers, retry, fallback ladder, circuit breakers, budgets, abstention).

> Honest status: see [ENGINEERING_AUDIT.md](ENGINEERING_AUDIT.md) and `python3 scripts/gate_report.py`. Several KPIs fail or are pending
> (reranker latency, RAGAS relevancy, 50K load) — they need hardware this project was not given. Nothing is marked PASS without evidence in `evidence/`.

## Quick start (local)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then set OPENROUTER_API_KEY (and JWT_SECRET / AUDIT_HASH_SEED: openssl rand -hex 32)
python3 scripts/build_corpus.py && python3 scripts/build_vault.py   # chunks + Obsidian vault + graph.json (already committed)
python3 scripts/export_onnx.py                                      # int8 ONNX models into models/ (not committed)
python3 scripts/train_triage.py                                     # only if models/triage_lr.npz is missing

# real pipeline API
DEMO_TENANTS=demo uvicorn assistant.main:app --port 8010
# developer workbench (6 tabs)
streamlit run app.py            # http://localhost:8501
```
Query: `curl -X POST localhost:8010/api/v1/agent/query -H 'Content-Type: application/json' -H 'X-Tenant-ID: demo' -d '{"tenant_id":"demo","user_id":"alice","query":"What is the RRF smoothing constant?"}'`

Auth: set `API_JWT_SECRET` (≥32 chars) to require HS256 bearer tokens carrying `tenant_id`; approval endpoints (`/api/v1/hitl/...`) need a token with `roles: ["approver"]` and refuse to run without a secret.

## Tests and scorecard
```bash
python3 -m pytest -q                 # fast suite (195 tests, no network)
python3 -m pytest -q -m slow         # real-model retrieval tests (~6 min on CPU)
python3 scripts/gate_report.py       # computed PASS/FAIL/PENDING scorecard from tests + evidence/
python3 scripts/eval_ragas.py        # live RAGAS-lite eval (~$0.07 of API credit, ~8 min)
scripts/run_load_tier.sh 5k 5        # k6 load tier against a running stub server (assistant.server:app)
```

## Layout
| Path | What |
|---|---|
| `design.md` | Architecture, contracts, latency budget, FMEA, ADRs, slice status |
| `assistant/router/` | Model Router: tiers, fallback ladder, breakers, budgets, providers |
| `assistant/plugins/` | PII redactor, injection shield, fail-closed plugin manager |
| `assistant/rag/` | Ingest, hybrid retriever, int8 ONNX models, (disabled) LLM reranker |
| `assistant/agent/` | Tool harness, bounded ReAct loop, HITL queue, subagents, generation + verification |
| `assistant/agents/` | Triage (rules + local classifier + LLM) |
| `assistant/release.py` | Versioned artifacts, flags, canary + auto-rollback |
| `assistant/cache.py`, `graphify.py` | Tenant-isolated semantic cache; Obsidian vault + depth≤2 pruning |
| `mcp_servers/` | MCP servers: hybrid-rag, graphify-vault |
| `redteam/`, `load_tests/`, `evidence/` | 100-prompt suite, k6/JMeter plans, measured evidence |
| `agents/` | Registry + contracts for the 13 agents/components |

## Known limits
Redis/Postgres/OTel exporter are in-memory stand-ins; the state store is an in-memory demo; Dockerfile/compose are not build-tested; remote-LLM latency is ~3–9 s per answer.
