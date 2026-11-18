"""Build the chunk corpus from the 3 source docs (tenant 'demo'). Output: data/chunks.jsonl"""
import json, sys
from pathlib import Path
sys.path.insert(0, ".")
from transformers import AutoTokenizer
from assistant.rag.ingest import chunk_document

tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
out = Path("data"); out.mkdir(exist_ok=True)
chunks = []
for f in sorted(Path(".").glob("*.docx")):
    cs = chunk_document(f, "demo", tok); chunks += cs; print(f.name, len(cs), "chunks")
with open(out / "chunks.jsonl", "w") as fh:
    for c in chunks: fh.write(json.dumps(c.__dict__) + "\n")
print("total", len(chunks))
