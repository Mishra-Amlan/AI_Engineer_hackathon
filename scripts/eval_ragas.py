import asyncio, json, sys, time, statistics
sys.path.insert(0, ".")
from sentence_transformers import CrossEncoder, SentenceTransformer
from assistant.agent.generation import GenerationPipeline, NO_INFO
from assistant.agent.harness import ToolHarness
from assistant.agent.subagents import ExecutionSubagent, RetrievalSubagent, retrieval_tool
from assistant.audit import AuditLog
from assistant.config import Settings
from assistant.eval_ragas import judge_answer
from assistant.orchestrator import Orchestrator
from assistant.plugins.base import PluginManager
from assistant.plugins.injection import InjectionShield
from assistant.plugins.pii import PiiRedactor
from assistant.rag.ingest import Chunk
from assistant.rag.retriever import HybridRetriever
from assistant.agents.triage import TriageAgent
from assistant.router.providers import OpenRouterProvider
from assistant.router.router import ModelRouter
from tests.golden import G
from tests.test_slice6 import build as build_tools

async def main():
    s = Settings.load(".env", {"DAILY_BUDGET_USD": "0.30", "PER_TENANT_DAILY_BUDGET_USD": "0.30", "ROUTER_REQUEST_TIMEOUT_MS": "30000"})
    router = ModelRouter(s, OpenRouterProvider(s.openrouter_api_key.get_secret_value(), s.openrouter_base_url))
    chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
    ret = HybridRetriever(chunks, SentenceTransformer("BAAI/bge-small-en-v1.5"), CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2"))
    h, q, audit = build_tools()
    o = Orchestrator(PluginManager([PiiRedactor(), InjectionShield()]), TriageAgent(router),
                     RetrievalSubagent(ToolHarness([retrieval_tool(ret, lambda: "demo", timeout_s=15)])), GenerationPipeline(router, s.model_verifier),
                     ExecutionSubagent(h, router, total_budget_ms=15000), audit)
    judge = s.model_t2_primary
    claims = sup = 0; rel = []; pos = neg = abst_ok = 0; modes = {}; ent = []; ungr = 0; lat = []; wrong_route = []; judge_fail = []
    for cat, qn, groups in G:
        t0 = time.perf_counter(); r = await o.handle("demo", "u", qn); lat.append((time.perf_counter() - t0) * 1000)
        modes[r.mode] = modes.get(r.mode, 0) + 1
        if groups is None:
            neg += 1; okk = r.abstained or r.route == "REJECT_OOS"; abst_ok += okk
            if not okk: print("  NEG answered:", qn, "->", r.text[:80])
            continue
        pos += 1
        if r.route != "HYBRID_RAG": wrong_route.append((qn, r.route)); continue
        if r.abstained: print("  ANSWERABLE abstained:", qn); rel.append(0.0); continue
        cites = {c["id"] for c in r.citations}
        ctx = [{"text": c.text} for c in chunks if c.id in cites] or [{"text": c.text} for c in chunks[:0]]
        j = await judge_answer(router, judge, qn, r.text, ctx)
        if j["f_reason"] or j["r_reason"]: judge_fail.append((qn, j["f_reason"], j["r_reason"]))
        if j["supported"] is not None: claims += j["claims"]; sup += j["supported"]
        if j["relevancy"] is not None:
            rel.append(j["relevancy"])
            if j["relevancy"] < 0.7: print("  LOW relevancy", j["relevancy"], qn, "|", r.text[:100])
        ungr += bool(j["ungrounded"])
        if j["supported"] is not None and j["supported"] < j["claims"]: print("  UNSUPPORTED claims:", qn, j["supported"], "/", j["claims"], "|", r.text[:120])
        txt = " ".join(c["text"] for c in ctx)
        ent.append(sum(any(x in txt for x in g) for g in groups) / len(groups))
    lat.sort()
    print(json.dumps({"faithfulness": round(sup / claims, 3) if claims else None, "hallucination_rate": round(1 - sup / claims, 3) if claims else None,
        "answer_relevancy": round(statistics.mean(rel or [0]), 3), "cited_context_entity_recall": round(statistics.mean(ent or [0]), 3),
        "abstention_accuracy": f"{abst_ok}/{neg}", "answers_with_ungrounded_values": ungr, "modes": modes, "wrong_route": wrong_route, "judge_failures": judge_fail, "answered": len(ent),
        "e2e_p50_ms": round(lat[len(lat)//2]), "e2e_p95_ms": round(lat[int(.95*len(lat))-1]), "spent_usd": round(router.budget.global_spent, 4)}, indent=1))
asyncio.run(main())
