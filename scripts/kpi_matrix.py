"""36-KPI matrix. Each KPI is bound to an executable test or an evidence file. PASS/FAIL/PENDING are computed, never hand-set."""
import json, subprocess, sys
from pathlib import Path

def ev(p):
    f = Path(p); return json.loads(f.read_text()) if f.exists() else None

def tests_pass(ids):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *ids], capture_output=True, text=True)
    return r.returncode == 0

T = "tests/"
rag, tri, ragas, tok = ev("evidence/slice4/retrieval.json"), ev("evidence/slice3/triage_live.json"), ev("evidence/slice7/ragas.json"), ev("evidence/tokens.json")
load = {t: ev(f"evidence/load/{t}.json") for t in ("5k", "10k", "50k")}
K = {}
def k(n, name, status, detail=""): K[n] = (name, status, detail)
P = lambda ok: "PASS" if ok else "FAIL"
k(1, "Pre-hook p95 <=15ms", P(tests_pass([T + "test_slice2.py::test_hook_latency_kpi01"])))
k(2, "PII recall >=99.8%", P(tests_pass([T + "test_slice2.py::test_pii_recall_kpi02", T + "test_slice11_redteam.py::test_cat4_pii_smuggling_redacted"])), "20+20 samples")
k(3, "Injection block >=99.5%", P(tests_pass([T + "test_slice2.py::test_injection_block_rate_kpi03", T + "test_slice11_redteam.py::test_cat1_direct_jailbreaks_blocked"])), "rules tuned alongside suite - not independent")
k(4, "Triage accuracy >=97%", P(tests_pass([T + "test_slice3_triage.py::test_rules_routing_accuracy_kpi04"]) and tri and tri["accuracy"] >= .97), f"live SLM {tri['accuracy']:.0%} on {tri['n']}" if tri else "")
tl = ev("evidence/slice3/triage_local.json")
k(5, "Triage p95 <=25ms", P(bool(tri) and tri["p95_ms"] <= 25), (f"LLM-only p95 {tri['p95_ms']} ms; with local cascade {tl['local_share']:.0%} of queries answered locally at p95 {tl['local_p95_ms']} ms, rest via LLM" if tl else f"live p95 {tri['p95_ms']} ms") if tri else "")
k(6, "False refusal <=1%", P(tests_pass([T + "test_slice2.py::test_injection_false_positive_kpi06", T + "test_slice11_redteam.py::test_zz_benign_control_set_no_false_refusals_kpi06"])))
k(7, "BM25 p95 <=12ms", P(bool(rag) and rag["bm25_p95_ms"] <= 12)); k(8, "Dense p95 <=25ms", P(bool(rag) and rag["dense_p95_ms"] <= 25), f"{rag['dense_p95_ms']} ms" if rag else "")
k(9, "Rerank p95 <=45ms", P(bool(rag) and rag["rerank_ms_40pairs_cpu"] <= 45), f"{rag['rerank_ms_40pairs_cpu']} ms CPU" if rag else "")
k(10, "Recall@50 >=0.92", P(bool(rag) and rag["recall50"] >= .92)); k(11, "Precision@4 >=0.88", P(bool(rag) and rag["precision_returned"] >= .88), f"{rag['precision_returned']}" if rag else "")
k(12, "MRR@4 >=0.85", P(bool(rag) and rag["mrr4"] >= .85)); k(13, "nDCG@4 >=0.86", P(bool(rag) and rag["ndcg4"] >= .86), f"{rag['ndcg4']}" if rag else "")
k(14, "Schema first-pass >=96%", "PENDING", "needs real traffic; unit mix is synthetic")
k(15, "Auto-repair >=90%", P(tests_pass([T + "test_slice5.py::test_kpi14_kpi15_validation_and_repair_rates"])), "synthetic mix")
k(16, "Loop escape 100%", P(tests_pass([T + "test_slice5.py::test_kpi16_infinite_loop_escape_100pct_chaos"])))
k(17, "Mean steps <=2.2", P(tests_pass([T + "test_slice5.py::test_kpi17_mean_steps_normal_tasks"])), "scripted tasks")
k(18, "Goal drift >=0.85", "PENDING", "not measured")
k(19, "HITL enforcement 100%", P(tests_pass([T + "test_slice6.py::test_kpi19_property_no_mutation_without_approval_100pct"])))
if ragas:
    k(20, "Faithfulness >=0.92", P(ragas["faithfulness"] >= .92), str(ragas["faithfulness"])); k(21, "Answer relevancy >=0.90", P(ragas["answer_relevancy"] >= .90), str(ragas["answer_relevancy"]))
    k(22, "Entity recall >=0.85", P(ragas["cited_context_entity_recall"] >= .85), str(ragas["cited_context_entity_recall"]))
    a, b = ragas["abstention_accuracy"].split("/"); k(23, "Abstention >=98%", P(a == b), ragas["abstention_accuracy"])
    k(24, "Hallucination <=0.5%", P(ragas["hallucination_rate"] <= .005), str(ragas["hallucination_rate"]))
else:
    for n, nm in [(20, "Faithfulness"), (21, "Relevancy"), (22, "Entity recall"), (23, "Abstention"), (24, "Hallucination")]: k(n, nm, "PENDING")
k(25, "TTFT p95 <=180ms", "PENDING", "no streaming yet")
k(26, "Token reduction >=45%", P(bool(tok) and tok["token_reduction"] >= .45 and tok["entity_recall_pruned"] >= .85), f"{tok['token_reduction']:.0%}, recall {tok['entity_recall_pruned']}" if tok else "")
k(27, "Cache hit >=35%", "PENDING", "load-test query mix is synthetic; needs production-like traffic")
k(28, "Cross-tenant leaks = 0", P(tests_pass([T + "test_slice9.py::test_kpi28_probe_many_tenants_zero_leaks", T + "test_api.py::test_concurrent_tenants_never_cross"])))
k(29, "Cost <=$0.45/1K", "PENDING", "needs production-mix measurement; dev RAGAS run incl. judge ~ $2.4/1K"); k(30, "MCP overhead <=4ms", "PENDING", "MCP server not benchmarked")
for n, nm, key in [(31, "p50 @50K <=240ms", "p50"), (32, "p95 @50K <=450ms", "p95"), (33, "p99 @50K <=590ms", "p99")]:
    k(n, nm, "PENDING" if not load["50k"] else P(load["50k"][key + "_ms"] <= {"p50": 240, "p95": 450, "p99": 590}[key]), "50K tier not run on this host")
k(34, "5xx <=0.05% @50K", "PENDING" if not load["50k"] else P(load["50k"]["err_rate"] <= .0005)); k(35, "RPS >=8500", "PENDING" if not load["50k"] else P(load["50k"]["rps"] >= 8500)); k(36, "RSS growth <=3%/1h", "PENDING", "1-hr soak not run")
out = {f"KPI-{n:02d}": {"name": v[0], "status": v[1], "detail": v[2]} for n, v in sorted(K.items())}
Path("evidence").mkdir(exist_ok=True); counts = {s: sum(v["status"] == s for v in out.values()) for s in ("PASS", "FAIL", "PENDING")}
Path("evidence/kpi_matrix.json").write_text(json.dumps({"counts": counts, "kpis": out}, indent=1))
for n, v in out.items(): print(f"{n} {v['status']:<8} {v['name']:<26} {v['detail']}")
print(counts)
