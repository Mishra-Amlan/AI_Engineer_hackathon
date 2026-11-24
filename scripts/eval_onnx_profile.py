import json, sys, time, statistics
sys.path.insert(0, ".")
from assistant.rag.ingest import Chunk
from assistant.rag.onnx_models import OnnxEmbedder, OnnxReranker
from assistant.rag.retriever import HybridRetriever, RetrievalParams
from scripts.eval_retrieval import evaluate
from tests.golden import G
chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
emb = OnnxEmbedder()
for pool, ml in ((40, 256), (12, 128), (8, 128)):
    r = HybridRetriever(chunks, emb, OnnxReranker(max_len=ml), RetrievalParams(pool=pool))
    out, p95, _ = evaluate(r, chunks, verbose=False)
    ab = sum(r.retrieve("demo", q).abstain for _, q, g in G if g is not None)
    print(f"pool={pool} max_len={ml}", {k: round(v, 3) if isinstance(v, float) else v for k, v in out.items()}, "stage p95 ms", {k: round(v, 1) for k, v in p95.items()}, "false_abstain", f"{ab}/29")
