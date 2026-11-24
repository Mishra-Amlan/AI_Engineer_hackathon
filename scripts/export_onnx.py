"""Export + int8-quantize the reranker and embedder for CPU. Usage: python scripts/export_onnx.py"""
import time, sys, torch
from pathlib import Path
from onnxruntime.quantization import QuantType, quantize_dynamic
from transformers import AutoModelForSequenceClassification, AutoModel, AutoTokenizer
out = Path("models"); out.mkdir(exist_ok=True)
def export(model, tok, path, pair):
    enc = tok(*pair, return_tensors="pt", padding=True, truncation=True, max_length=256)
    names = [k for k in ("input_ids", "attention_mask", "token_type_ids") if k in enc]
    model.eval()
    torch.onnx.export(model, tuple(enc[k] for k in names), str(path), input_names=names, output_names=["out"],
        dynamic_axes={**{k: {0: "b", 1: "s"} for k in names}, "out": {0: "b"}}, opset_version=17, dynamo=False)
    q = path.with_name(path.stem + "_int8.onnx"); quantize_dynamic(str(path), str(q), weight_type=QuantType.QInt8); return q
name = "cross-encoder/ms-marco-MiniLM-L-6-v2"; tok = AutoTokenizer.from_pretrained(name)
print(export(AutoModelForSequenceClassification.from_pretrained(name), tok, out / "reranker.onnx", (["q"], ["d"])))
name = "BAAI/bge-small-en-v1.5"; tok = AutoTokenizer.from_pretrained(name)
class Emb(torch.nn.Module):
    def __init__(self): super().__init__(); self.m = AutoModel.from_pretrained(name)
    def forward(self, input_ids, attention_mask, token_type_ids): return self.m(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids).last_hidden_state[:, 0]
print(export(Emb(), tok, out / "embedder.onnx", (["hello world"],)))
