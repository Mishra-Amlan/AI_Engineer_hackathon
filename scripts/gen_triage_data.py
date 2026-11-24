"""Generate synthetic labeled triage queries with the router (cheap). Run once; output data/triage_train.jsonl"""
import asyncio, json, sys
sys.path.insert(0, ".")
from pydantic import BaseModel
from assistant.config import Settings
from assistant.router.providers import OpenRouterProvider
from assistant.router.router import ModelRouter
from assistant.router.types import Message, RouterRequest, Tier

class Out(BaseModel): queries: list[str]
SPECS = {
 "smalltalk": "greetings, thanks, goodbyes, 'who are you', 'what can you do' style messages",
 "policy_question": "questions about company policies, SOPs, compliance rules, procedures, AND technical questions about an AI-assistant system's architecture (RAG retrieval, reranking, agents, KPIs, load testing, security, observability, fine-tuning small language models, model licenses, hyperparameters)",
 "lookup": "read-only requests to check the status/quantity/details of a specific SKU-### or LOT-##### item, batch or order (use formats like SKU-099, sku99, LOT-00044, lot 44)",
 "transaction": "imperative requests to CHANGE state: approve/release/quarantine/recall/cancel/update/delete/move a specific SKU, LOT, batch, order or shipment",
 "out_of_scope": "requests unrelated to the business: weather, jokes, sports, recipes, celebrity trivia, personal advice, salaries of executives, poems, general knowledge",
}
async def main():
    s = Settings.load(".env", {"DAILY_BUDGET_USD": "0.5", "PER_TENANT_DAILY_BUDGET_USD": "0.5", "ROUTER_REQUEST_TIMEOUT_MS": "60000", "MAX_OUTPUT_TOKENS": "2000", "PER_REQUEST_MAX_TOKENS": "4000"})
    r = ModelRouter(s, OpenRouterProvider(s.openrouter_api_key.get_secret_value(), s.openrouter_base_url))
    rows = []
    for intent, desc in SPECS.items():
        for batch in range(4):
            resp = await r.complete(RouterRequest(tenant_id="gen", tier=Tier.T2, json_schema=Out, temperature=0.9, max_tokens=1800,
                messages=[Message(role="user", content=f"Write 40 diverse, realistic user messages of this kind: {desc}. Vary length (3 to 30 words), tone, typos, casing and phrasing. Batch #{batch+1}: make them different from typical examples. Reply ONLY JSON: {{\"queries\": [...]}}")]))
            if resp.parsed: rows += [{"q": q.strip(), "intent": intent} for q in resp.parsed["queries"] if 3 <= len(q) <= 300]
        print(intent, sum(x["intent"] == intent for x in rows), flush=True)
    seen, out = set(), []
    for x in rows:
        k = x["q"].lower()
        if k not in seen: seen.add(k); out.append(x)
    open("data/triage_train.jsonl", "w").write("\n".join(json.dumps(x) for x in out)); print("total", len(out), "cost", round(r.budget.global_spent, 4))
asyncio.run(main())
