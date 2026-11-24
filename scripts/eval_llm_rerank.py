import json, sys
sys.path.insert(0, ".")
from assistant.config import Settings
from assistant.rag.ingest import Chunk
from assistant.rag.llm_rerank import LLMReranker
from assistant.rag.onnx_models import OnnxEmbedder
from assistant.rag.retriever import HybridRetriever, RetrievalParams
from assistant.router.providers import OpenRouterProvider
from assistant.router.router import ModelRouter
from scripts.eval_retrieval import evaluate
from tests.golden import G
s = Settings.load(".env", {"DAILY_BUDGET_USD": "0.2", "PER_TENANT_DAILY_BUDGET_USD": "0.2", "ROUTER_REQUEST_TIMEOUT_MS": "30000"})
router = ModelRouter(s, OpenRouterProvider(s.openrouter_api_key.get_secret_value(), s.openrouter_base_url))
chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
for pool in (12,):
    r = HybridRetriever(chunks, OnnxEmbedder(), LLMReranker(router, pool=pool), RetrievalParams(pool=40, agreement_rescue=False))
    out, p95, miss = evaluate(r, chunks, verbose=True)
    ab = [q for _, q, g in G if g is not None and r.retrieve("demo", q).abstain]
    print(f"LLM rerank pool={pool}:", {k: round(v, 3) if isinstance(v, float) else v for k, v in out.items()}, "false_abstain", len(ab), "/29", "rerank p95 ms", round(p95["rag.rerank"]), "cost $", round(router.budget.global_spent, 4))
