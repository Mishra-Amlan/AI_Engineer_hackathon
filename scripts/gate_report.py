"""Evidence-driven gate scorecard. Status is COMPUTED from evidence files / live checks — never hand-set.
PASS = measured and meets threshold | FAIL = measured and misses | PENDING = no evidence yet."""
import json, subprocess, sys
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

rows = []
def row(gate, evidence, status, detail=""):
    rows.append((gate, evidence, status, detail))

# unit + contract tests
p = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
last = [l for l in p.stdout.strip().splitlines() if "passed" in l or "failed" in l]
row("Unit and tool contracts", "Pytest suite (fast)", "PASS" if p.returncode == 0 else "FAIL", last[-1] if last else "")
# syntax
c = run([sys.executable, "-m", "compileall", "-q", "assistant", "scripts", "tests", "mcp_servers"])
row("Python syntax", "compileall application, scripts, tests", "PASS" if c.returncode == 0 else "FAIL")
# RAGAS
f = Path("evidence/slice7/ragas.json")
if f.exists():
    d = json.loads(f.read_text())
    checks = {"faithfulness>=0.92": d["faithfulness"] >= .92, "relevancy>=0.90": d["answer_relevancy"] >= .90,
              "entity_recall>=0.85": d["cited_context_entity_recall"] >= .85, "abstain 100%": d["abstention_accuracy"].split("/")[0] == d["abstention_accuracy"].split("/")[1],
              "hallucination<=0.5%": d["hallucination_rate"] <= .005}
    fails = [k for k, v in checks.items() if not v]
    row("RAGAS golden set (34 q, proxy judge)", "Faithfulness, relevancy, entity recall, abstention", "PASS" if not fails else "FAIL", "failing: " + ", ".join(fails) if fails else "")
else:
    row("RAGAS golden set", "Faithfulness, relevancy, precision, recall, entity recall", "PENDING")
# gates with no evidence yet
for g, e in [("100-prompt red-team suite", "100 prompts across 5 categories"), ("Live API and tenant isolation", "Health 200, query 200, tenant retained"),
             ("5K load tier", "Latency, 5xx, isolation, correctness"), ("10K load tier", "Saturation and contention evidence"),
             ("50K load tier", "p50/p95/p99, throughput, 5xx, soak"), ("JMeter validation", "Independent controller/worker evidence"),
             ("36-KPI matrix", "All stage-level thresholds")]:
    ev = Path("evidence") / (g.split()[0].lower() + ".json")
    row(g, e, "PENDING" if not ev.exists() else json.loads(ev.read_text()).get("status", "PENDING"))
w = max(len(r[0]) for r in rows)
print(f"{'Gate':<{w}}  {'Status':<8}  Required Evidence")
for g, e, s, d in rows: print(f"{g:<{w}}  {s:<8}  {e}" + (f"  [{d}]" if d else ""))
sys.exit(0 if all(r[2] == "PASS" for r in rows) else 1)
