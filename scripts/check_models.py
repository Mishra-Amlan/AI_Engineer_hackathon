import json, sys, urllib.request
sys.path.insert(0, ".")
from assistant.config import Settings
s = Settings.load(".env", {})
data = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20))["data"]
by = {m["id"]: m for m in data}
for name in ["model_t1_primary","model_t1_fallback","model_t2_primary","model_t2_fallback","model_t3_primary","model_t3_fallback","model_verifier"]:
    mid = getattr(s, name); m = by.get(mid)
    if m: p = m["pricing"]; print(f"OK   {name:18} {mid:40} in=${float(p['prompt'])*1e6:.3f}/M out=${float(p['completion'])*1e6:.3f}/M ctx={m.get('context_length')}")
    else: print(f"MISS {name:18} {mid}")
