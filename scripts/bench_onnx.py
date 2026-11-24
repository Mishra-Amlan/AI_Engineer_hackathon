import json, sys, time, statistics
sys.path.insert(0, ".")
import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer
from assistant.rag.ingest import Chunk
from assistant.rag.onnx_models import OnnxEmbedder, OnnxReranker
chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
q = "What is the RRF smoothing constant?"; docs = [c.text for c in chunks[:40]]
def t(f, n=15):
    f(); xs = []
    for _ in range(n): s = time.perf_counter(); f(); xs.append((time.perf_counter() - s) * 1000)
    xs.sort(); return round(statistics.median(xs), 1), round(xs[int(.95 * n) - 1], 1)
ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
for ml in (256, 128):
    oe = OnnxReranker(max_len=ml)
    for k in (40, 12):
        print(f"rerank int8 max_len={ml} pairs={k}: median/p95 ms", t(lambda: oe.predict([(q, d) for d in docs[:k]])))
print("rerank torch fp32 40 pairs:", t(lambda: ce.predict([(q, d) for d in docs], batch_size=32), 3))
a, b = np.array(ce.predict([(q, d) for d in docs])), np.array(OnnxReranker(max_len=256).predict([(q, d) for d in docs]))
print("score correlation torch vs int8:", round(float(np.corrcoef(a, b)[0, 1]), 4), "top-4 overlap:", len(set(np.argsort(-a)[:4]) & set(np.argsort(-b)[:4])))
st, oem = SentenceTransformer("BAAI/bge-small-en-v1.5"), OnnxEmbedder()
pq = "Represent this sentence for searching relevant passages: " + q
print("query embed torch:", t(lambda: st.encode([pq], normalize_embeddings=True)), " onnx int8:", t(lambda: oem.encode([pq])))
va, vb = st.encode([pq], normalize_embeddings=True)[0], oem.encode([pq])[0]; print("embed cosine torch vs int8:", round(float(va @ vb), 4))
