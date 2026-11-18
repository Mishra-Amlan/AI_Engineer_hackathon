import json, sys, statistics
sys.path.insert(0, ".")
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
from assistant.graphify import Graph, count_tokens, prune_context
from assistant.rag.ingest import Chunk
from assistant.rag.retriever import HybridRetriever
from tests.golden import G
tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
class NoCE:                              # first-stage only: measuring prompt size, not rerank quality
    def predict(self, pairs, batch_size=32): return [0.0] * len(pairs)
r = HybridRetriever(chunks, SentenceTransformer("BAAI/bge-small-en-v1.5"), NoCE()); g = Graph()
base_t, opt_t, rb, ro = [], [], [], []
for cat, q, groups in G:
    if groups is None: continue
    res = r.retrieve("demo", q, None); fused = res.candidates["fused"]
    raw = " ".join(next(c.text for c in chunks if c.id == i) for i in fused[:8])        # baseline: raw top-8 chunk dump
    ctx, info = prune_context(g, q, fused[:4], tok, depth=2, budget=int(sys.argv[1]) if len(sys.argv) > 1 else 320)
    base_t.append(count_tokens(tok, raw)); opt_t.append(count_tokens(tok, ctx))
    rb.append(sum(any(s in raw for s in grp) for grp in groups) / len(groups)); ro.append(sum(any(s in ctx for s in grp) for grp in groups) / len(groups))
red = 1 - sum(opt_t) / sum(base_t)
out = {"baseline_tokens_mean": round(statistics.mean(base_t)), "optimized_tokens_mean": round(statistics.mean(opt_t)), "token_reduction": round(red, 3),
       "entity_recall_baseline": round(statistics.mean(rb), 3), "entity_recall_pruned": round(statistics.mean(ro), 3), "n": len(base_t)}
print(json.dumps(out)); json.dump(out, open("evidence/tokens.json", "w"))
