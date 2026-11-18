import json
from pathlib import Path
from assistant.graphify import Graph, Note, build_notes, prune_context, write_vault
from assistant.rag.ingest import Chunk
from transformers import AutoTokenizer

def chunks():
    return [Chunk(f"d#{i:04d}", "demo", "d", f"S{i}", t, f"h{i}") for i, t in enumerate([
        "Intro section about the system. KPI-26 measures prompt token reduction.",
        "RRF smoothing constant k = 60; dedup by chunk_hash; pool = 40; KPI-10 recall.",
        "Circuit breaker trips after 2 identical failures; HITL approval required for tier 3.",
        "Load test uses k6 with 50,000 VUs and p99 under 600 ms.",
        "Unrelated appendix about fonts and colors.",
        "Graphify traverses depth 2 and KPI-26 is the token KPI."])]

def test_vault_frontmatter_and_valid_wikilinks(tmp_path):
    ns = build_notes(chunks()); write_vault(ns, tmp_path / "v", tmp_path / "g.json")
    files = list((tmp_path / "v").glob("*.md")); assert len(files) == 6
    t = files[0].read_text(); assert t.startswith("---\nid:") and "risk_tier:" in t and "version:" in t and "domain:" in t
    ids = {f.stem for f in files}
    import re
    for f in files:
        for l in re.findall(r"\[\[([^\]]+)\]\]", f.read_text()): assert l in ids, l
    assert next(n for n in ns if "HITL" in n.body).risk_tier == 3

def test_cross_links_connect_shared_rare_terms(tmp_path):
    ns = build_notes(chunks()); n0 = next(n for n in ns if n.id == "d#0000")
    assert "d#0005" in n0.links                                      # both mention KPI-26

def test_traversal_depth_hard_capped_at_2(tmp_path):
    ns = [Note(f"n{i}", "x", 1, "v1", "t", f"body {i}", [f"n{i+1}"] if i < 5 else []) for i in range(6)]
    write_vault(ns, tmp_path / "v", tmp_path / "g.json"); g = Graph(tmp_path / "g.json")
    assert set(g.neighborhood(["n0"], depth=99)) == {"n0", "n1", "n2"}
    assert set(g.neighborhood(["n3"], depth=1)) == {"n2", "n3", "n4"}

def test_prune_respects_budget_prefers_relevant_and_cuts_tokens(tmp_path):
    ns = build_notes(chunks()); write_vault(ns, tmp_path / "v", tmp_path / "g.json"); g = Graph(tmp_path / "g.json")
    tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
    ctx, info = prune_context(g, "what is the RRF smoothing constant", ["d#0001"], tok, budget=40)
    assert info["tokens"] <= 40 and "k = 60" in ctx and "fonts" not in ctx
    raw = " ".join(c.text for c in chunks())
    assert len(tok.encode(ctx)) < len(tok.encode(raw)) * 0.55

def test_real_vault_kpi26_evidence_if_present():
    p = Path("evidence/tokens.json")
    if p.exists():
        d = json.loads(p.read_text()); assert d["token_reduction"] >= 0.45 and d["entity_recall_pruned"] >= 0.85
