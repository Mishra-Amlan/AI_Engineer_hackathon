"""CPU int8 ONNX drop-ins for CrossEncoder.predict and SentenceTransformer.encode."""
from __future__ import annotations
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer


def _session(path: str, threads: int):
    o = ort.SessionOptions(); o.intra_op_num_threads = threads; o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(path, o, providers=["CPUExecutionProvider"])


class OnnxReranker:
    def __init__(self, path="models/reranker_int8.onnx", tokenizer="cross-encoder/ms-marco-MiniLM-L-6-v2", max_len=256, threads=4):
        self.s, self.tok, self.max_len = _session(path, threads), AutoTokenizer.from_pretrained(tokenizer), max_len
        self.names = {i.name for i in self.s.get_inputs()}

    def predict(self, pairs, batch_size=32):
        out = []
        for i in range(0, len(pairs), batch_size):
            b = pairs[i:i + batch_size]
            enc = self.tok([q for q, _ in b], [d for _, d in b], padding=True, truncation="only_second", max_length=self.max_len, return_tensors="np")
            out.extend(self.s.run(None, {k: v.astype("int64") for k, v in enc.items() if k in self.names})[0].reshape(len(b), -1)[:, 0].tolist())
        return out


class OnnxEmbedder:
    def __init__(self, path="models/embedder_int8.onnx", tokenizer="BAAI/bge-small-en-v1.5", max_len=256, threads=4):
        self.s, self.tok, self.max_len = _session(path, threads), AutoTokenizer.from_pretrained(tokenizer), max_len
        self.names = {i.name for i in self.s.get_inputs()}

    def encode(self, texts, normalize_embeddings=True, batch_size=32, convert_to_numpy=True):
        rows = []
        for i in range(0, len(texts), batch_size):
            enc = self.tok(texts[i:i + batch_size], padding=True, truncation=True, max_length=self.max_len, return_tensors="np")
            rows.append(self.s.run(None, {k: v.astype("int64") for k, v in enc.items() if k in self.names})[0])
        v = np.vstack(rows).astype("float32")
        return v / np.linalg.norm(v, axis=1, keepdims=True) if normalize_embeddings else v
