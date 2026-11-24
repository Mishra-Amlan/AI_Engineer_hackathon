import json, sys
from pathlib import Path
tier, think = sys.argv[1], float(sys.argv[2])
m = json.loads(Path(f"evidence/load/{tier}_raw.json").read_text())["metrics"]
d = m["http_req_duration"]; reqs = m["http_reqs"]
out = {"tier": tier, "vus": {"1k": 1000, "5k": 5000, "10k": 10000, "20k": 20000, "50k-conc": 50000}[tier], "think_s": think, "p50_ms": round(d["p(50)"], 2), "p95_ms": round(d["p(95)"], 2), "p99_ms": round(d["p(99)"], 2),
       "max_ms": round(d["max"], 1), "rps": round(reqs["rate"], 1), "requests": reqs["count"], "err_rate": m["http_req_failed"]["value"],
       "cache_hit_ratio": round(m["cache_hit"]["value"], 3) if "cache_hit" in m else None,
       "checks_pass_rate": m["checks"]["value"],
       "conditions": "single 4-core host; k6, 4 uvicorn workers, Streamlit idle; STUB model 40ms (simulated); real PII/injection hooks"}
out["status"] = "PASS" if (out["p50_ms"] <= 250 and out["p95_ms"] <= 450 and out["p99_ms"] <= 600 and out["err_rate"] <= 0.0005 and out["checks_pass_rate"] > 0.999) else "FAIL"
Path(f"evidence/load/{tier}.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out))
