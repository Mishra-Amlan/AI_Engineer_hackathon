"""Evidence-driven gate scorecard. Status is COMPUTED from evidence files / live checks — never hand-set.
PASS = measured and meets threshold | FAIL = measured and misses | PENDING = no evidence yet."""
import json, subprocess, sys
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

rows = []
P2 = lambda ok: "PASS" if ok else "FAIL"
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
# live API + tenant isolation (only if the stub server is up)
import urllib.request
def live_api():
    try:
        h = urllib.request.urlopen("http://localhost:8000/health", timeout=3).status
        req = urllib.request.Request("http://localhost:8000/api/v1/agent/query", data=json.dumps({"tenant_id": "tenant_9", "user_id": "u", "query": "hi"}).encode(),
                                     headers={"Content-Type": "application/json", "X-Tenant-ID": "tenant_9"})
        r = urllib.request.urlopen(req, timeout=5); body = json.loads(r.read())
        bad = urllib.request.Request("http://localhost:8000/api/v1/agent/query", data=req.data, headers={"Content-Type": "application/json", "X-Tenant-ID": "tenant_1"})
        try: urllib.request.urlopen(bad, timeout=5); blocked = False
        except urllib.error.HTTPError as e: blocked = e.code == 403
        return h == 200 and r.status == 200 and body["tenant_id"] == "tenant_9" and blocked
    except Exception: return None
import time as _t
_proc = None
if live_api() is None:                                     # self-contained: boot a temporary stub server
    _proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "assistant.server:app", "--port", "8000", "--log-level", "warning"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        _t.sleep(0.25)
        if live_api() is not None: break
la = live_api()
if _proc: _proc.terminate()
row("Live API and tenant isolation", "Health 200, query 200, tenant retained, mismatch 403", "PENDING" if la is None else P2(la), "server not running" if la is None else "")
rt = Path("evidence/100-prompt.json")
row("100-prompt red-team suite", "100 prompts across 5 categories", json.loads(rt.read_text())["status"] if rt.exists() else "PENDING")
for tier, label in [("5k", "5K load tier"), ("10k", "10K load tier"), ("20k", "20K concurrent (low RPS)"), ("50k-conc", "50K concurrent connections"), ("50k", "50K load tier")]:
    f = Path(f"evidence/load/{tier}.json")
    if f.exists():
        d = json.loads(f.read_text())
        if d.get("status") == "ABORTED": row(label, "Connections held, latency, 5xx", "PENDING", "aborted: " + d["reason"][:90]); continue
        row(label + " (stub model)", "Latency, 5xx, isolation, correctness", d["status"], f"p95 {d['p95_ms']} ms, p99 {d['p99_ms']} ms, {d['rps']} rps, err {d['err_rate']:.2%}")
    else: row(label, "p50/p95/p99, throughput, 5xx, soak", "PENDING", "not run on this host" if tier == "50k" else "")
row("JMeter validation", "Independent controller/worker evidence", "PENDING", "plan written; JMeter not installed")
km = subprocess.run([sys.executable, "scripts/kpi_matrix.py"], capture_output=True, text=True)
kd = json.loads(Path("evidence/kpi_matrix.json").read_text())["counts"]
row("36-KPI matrix", "All stage-level thresholds", "PASS" if kd["PASS"] == 36 else ("FAIL" if kd["FAIL"] else "PENDING"), f"{kd['PASS']} pass / {kd['FAIL']} fail / {kd['PENDING']} pending")
w = max(len(r[0]) for r in rows)
print(f"{'Gate':<{w}}  {'Status':<8}  Required Evidence")
for g, e, s, d in rows: print(f"{g:<{w}}  {s:<8}  {e}" + (f"  [{d}]" if d else ""))
sys.exit(0 if all(r[2] == "PASS" for r in rows) else 1)
