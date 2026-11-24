"""Distilled local triage classifier: int8 ONNX embedding + softmax regression (numpy). No network; target <=25 ms."""
from __future__ import annotations
import numpy as np

INTENTS = ["smalltalk", "policy_question", "lookup", "transaction", "out_of_scope"]


class LocalTriage:
    def __init__(self, embedder, path: str = "models/triage_lr.npz"):
        d = np.load(path, allow_pickle=True)
        self.W, self.b, self.classes, self.emb = d["W"], d["b"], list(d["classes"]), embedder

    def predict(self, text: str) -> tuple[str, float]:
        v = self.emb.encode([text], normalize_embeddings=True)[0]
        z = self.W @ v + self.b; z = z - z.max(); p = np.exp(z) / np.exp(z).sum()
        i = int(p.argmax()); return self.classes[i], float(p[i])
