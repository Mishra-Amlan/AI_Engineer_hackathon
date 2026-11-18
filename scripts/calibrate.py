import sys, json
sys.path.insert(0, ".")
from scripts.eval_retrieval import *

class Memo:
    def __init__(self, ce): self.ce, self.c = ce, {}
    def predict(self, pairs, batch_size=32):
        miss = [p for p in pairs if p not in self.c]
        if miss:
            for p, s in zip(miss, self.ce.predict(miss, batch_size=batch_size)): self.c[p] = s
        return [self.c[p] for p in pairs]

emb = SentenceTransformer("BAAI/bge-small-en-v1.5"); ce = Memo(CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2"))
chunks = load(); r = HybridRetriever(chunks, emb, ce); print("chunks", len(r.chunks), "quarantined", len(r.quarantined), flush=True)
for th in (0.42,):
    r.p.threshold = th; out, p95, miss = evaluate(r, chunks, verbose=False)
    print(th, {k: round(v, 3) if v is not None else v for k, v in out.items()}, "misses:", miss, flush=True)
# score separation answerable vs negative (top confidence)
import numpy as np
pos, neg = [], []
for cat, q, g in G:
    (neg if g is None else pos).append(r.retrieve("demo", q).confidence)
print("answerable conf  min/median:", round(min(pos), 4), round(float(np.median(pos)), 4), " negative conf max:", round(max(neg), 4))
ab = [q for c, q, g in G if g is not None and r.retrieve("demo", q).abstain]
lc = [q for c, q, g in G if g is not None and r.retrieve("demo", q).low_confidence]
print("answerable-but-abstained:", len(ab), ab, "| rescued(low_confidence):", len(lc))
