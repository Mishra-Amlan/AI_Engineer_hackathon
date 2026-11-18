import json, sys
sys.path.insert(0, ".")
from assistant.graphify import build_notes, write_vault
from assistant.rag.ingest import Chunk
chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
notes = build_notes(chunks); write_vault(notes)
deg = [len(n.links) for n in notes]
print(f"{len(notes)} notes, links avg {sum(deg)/len(deg):.1f}, max {max(deg)}, isolated {sum(d==0 for d in deg)}")
