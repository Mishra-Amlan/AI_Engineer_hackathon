import json, sys, time, statistics
sys.path.insert(0, ".")
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from assistant.agents.local_triage import LocalTriage
from assistant.agents.triage import Route, route_for, rules_classify, TriageModelOut
from assistant.rag.onnx_models import OnnxEmbedder
from tests.test_slice3_triage import LABELED
emb = OnnxEmbedder(); rows = [json.loads(l) for l in open("data/triage_train.jsonl")]
held = {q.lower() for q, _ in LABELED}; rows = [r for r in rows if r["q"].lower() not in held]       # never train on the hand-written test set
X = emb.encode([r["q"] for r in rows]); y = np.array([r["intent"] for r in rows])
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=0)
clf = LogisticRegression(C=20, max_iter=2000).fit(Xtr, ytr); print("synthetic held-out intent accuracy:", round(clf.score(Xte, yte), 4), "n =", len(yte))
clf = LogisticRegression(C=20, max_iter=2000).fit(X, y)
np.savez("models/triage_lr.npz", W=clf.coef_, b=clf.intercept_, classes=np.array(clf.classes_, dtype=object))
lt = LocalTriage(emb); ROUTE = {"smalltalk": Route.DIRECT_ANSWER, "policy_question": Route.HYBRID_RAG, "lookup": Route.HYBRID_RAG, "transaction": Route.TRANSACTION_EXEC, "out_of_scope": Route.REJECT_OOS}
ok, wrong, conf = 0, [], []
for q, exp in LABELED:
    i, p = lt.predict(q); r = ROUTE[i]; conf.append(p)
    ok += r == exp
    if r != exp: wrong.append((q, i, round(p, 2), exp.value))
print(f"hand-written labeled routes: {ok}/{len(LABELED)} = {ok/len(LABELED):.1%}", "min conf", round(min(conf), 2)); [print("  MISS", w) for w in wrong]
lat = []
for q, _ in LABELED * 5:
    t = time.perf_counter(); lt.predict(q); lat.append((time.perf_counter() - t) * 1000)
lat.sort(); print(f"latency ms p50={lat[len(lat)//2]:.1f} p95={lat[int(.95*len(lat))-1]:.1f}")
