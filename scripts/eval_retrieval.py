import json, sys, time, math
sys.path.insert(0, ".")
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from assistant.rag.ingest import Chunk
from assistant.rag.retriever import HybridRetriever, RetrievalParams
from tests.golden import G

def load():
    return [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]

def rel_ids(chunks, groups):
    return [{c.id for c in chunks if any(s in c.text for s in g)} for g in groups]

def evaluate(r, chunks, verbose=True):
    rec = mrr = ndcg = prec = n = 0; nneg = okneg = 0; lat = {k: [] for k in ("rag.bm25","rag.dense","rag.rrf","rag.rerank")}; miss=[]
    for cat, q, groups in G:
        res = r.retrieve("demo", q)
        for k in lat: lat[k].append(res.timings_ms[k])
        if groups is None:
            nneg += 1; okneg += res.abstain
            if not res.abstain and verbose: print("  NEG not abstained:", q, round(res.confidence, 3))
            continue
        rs = rel_ids(chunks, groups); n += 1
        if any(not g for g in rs): print("  !! no relevant chunk exists for:", q); 
        union = set(res.candidates["bm25"]) | set(res.candidates["dense"])
        rec += all(g & union for g in rs)
        final = res.candidates["final"]; allrel = set().union(*rs)
        rank = next((i for i, c in enumerate(final, 1) if c in allrel), None)
        mrr += 1 / rank if rank else 0
        dcg = sum(1 / math.log2(i + 1) for i, c in enumerate(final, 1) if c in allrel)
        idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(allrel), 4) + 1))
        ndcg += dcg / idcg if idcg else 0
        got = [h.chunk.id for h in res.hits]; prec += (sum(c in allrel for c in got) / len(got)) if got else 0
        if not rank and verbose: miss.append(q)
        if res.abstain and verbose: print("  ANSWERABLE but abstained:", q, round(res.confidence, 3))
    out = dict(recall50=rec/n, mrr4=mrr/n, ndcg4=ndcg/n, precision_returned=prec/n, abstain_acc=okneg/nneg if nneg else None, n=n, nneg=nneg)
    p95 = {k: sorted(v)[int(.95*len(v))-1] for k, v in lat.items()}
    return out, p95, miss

if __name__ == "__main__":
    emb = SentenceTransformer("BAAI/bge-small-en-v1.5")
    ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    chunks = load(); r = HybridRetriever(chunks, emb, ce)
    print("chunks", len(r.chunks), "quarantined", len(r.quarantined))
    for th in ([float(sys.argv[1])] if len(sys.argv) > 1 else [0.42]):
        r.p.threshold = th; out, p95, miss = evaluate(r, chunks); print("threshold", th, out, {k: round(v,1) for k,v in p95.items()}, "misses", miss)
