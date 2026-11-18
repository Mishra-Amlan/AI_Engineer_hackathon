"""Obsidian-style atomic notes + wikilink graph + depth<=2 subgraph pruning (Gate 17). Deterministic, no model calls."""
from __future__ import annotations
import json
import math
import re
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from .rag.retriever import tokenize

_TERM = re.compile(r"\b(?:KPI-\d+|Gate \d+|ADR-\d+|[A-Z][A-Z0-9_]{3,}|[a-z]+_[a-z_]+|[A-Za-z]+-\d+)\b")
_SENT = re.compile(r"(?<=[.!?;])\s+|\s+\|\s+|;\s+(?=[A-Z])")


@dataclass
class Note:
    id: str
    domain: str
    risk_tier: int
    version: str
    title: str
    body: str
    links: list[str]

    def to_markdown(self) -> str:
        fm = f"---\nid: {self.id}\ndomain: {self.domain}\nrisk_tier: {self.risk_tier}\nversion: {self.version}\n---\n"
        return fm + f"# {self.title}\n\n{self.body}\n\n## Related\n" + "\n".join(f"- [[{l.replace(chr(35), chr(95))}]]" for l in self.links) + "\n"


def build_notes(chunks, version: str = "v1", max_cross: int = 3) -> list[Note]:
    terms = {c.id: set(_TERM.findall(c.text)) for c in chunks}
    df = Counter(t for ts in terms.values() for t in ts)
    notes, by_src = [], {}
    for c in chunks: by_src.setdefault(c.source, []).append(c)
    for src, cs in by_src.items():
        for i, c in enumerate(cs):
            links = []
            if i > 0: links.append(cs[i - 1].id)
            if i < len(cs) - 1: links.append(cs[i + 1].id)
            cross = sorted(((sum(1 / math.log(1 + df[t]) for t in terms[c.id] & terms[o.id] if df[t] <= 6), o.id)
                            for o in chunks if o.id != c.id and o.id not in links), reverse=True)
            links += [oid for s, oid in cross[:max_cross] if s > 0.8]
            body = re.sub(r"^\[[^\]]*\]\s*", "", c.text)
            notes.append(Note(c.id, "engineering" if "SLM" not in src else "slm", 3 if re.search(r"HITL|mutat|approval", c.text, re.I) else 1,
                              version, c.section or src, body, links))
    return notes


def write_vault(notes: list[Note], out: str | Path = "knowledge_vault", graph_path: str | Path = "graph.json") -> None:
    out = Path(out); out.mkdir(exist_ok=True)
    for n in notes: (out / f"{n.id.replace('#', '_')}.md").write_text(n.to_markdown())
    Path(graph_path).write_text(json.dumps({"version": notes[0].version, "nodes": {n.id: {"title": n.title, "domain": n.domain, "risk_tier": n.risk_tier,
        "body": n.body, "links": n.links} for n in notes}}, indent=0))


class Graph:
    def __init__(self, path: str | Path = "graph.json"):
        d = json.loads(Path(path).read_text()); self.nodes = d["nodes"]; self.version = d["version"]
        self.adj: dict[str, set[str]] = {k: set() for k in self.nodes}
        for k, n in self.nodes.items():
            for l in n["links"]:
                if l in self.nodes: self.adj[k].add(l); self.adj[l].add(k)

    def neighborhood(self, anchors: list[str], depth: int = 2) -> dict[str, int]:
        depth = min(depth, 2)                                     # hard cap (Gate 17)
        dist = {a: 0 for a in anchors if a in self.nodes}; q = deque(dist)
        while q:
            u = q.popleft()
            if dist[u] >= depth: continue
            for v in self.adj[u]:
                if v not in dist: dist[v] = dist[u] + 1; q.append(v)
        return dist


def count_tokens(tokenizer, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))


def prune_context(graph: Graph, query: str, anchors: list[str], tokenizer, depth: int = 2, budget: int = 320) -> tuple[str, dict]:
    """Greedy sentence packing over the <=2-hop neighborhood: score = query-term overlap * hop decay; anchors guaranteed first."""
    qt = set(tokenize(query)); dist = graph.neighborhood(anchors, depth)
    cands = []
    for nid, d in dist.items():
        for s in (x.strip() for x in _SENT.split(graph.nodes[nid]["body"]) if x and len(x.strip()) > 12):
            ov = len(qt & set(tokenize(s))) / (len(qt) or 1)
            cands.append((ov * (1.0 if d == 0 else 0.6 if d == 1 else 0.35) + (0.05 if d == 0 else 0), nid, s))
    cands.sort(key=lambda x: -x[0])
    out, used, picked = [], 0, []
    for sc, nid, s in cands:
        if sc <= 0.05 and picked: break
        n = count_tokens(tokenizer, s)
        if used + n > budget: continue
        out.append((nid, s)); used += n; picked.append(nid)
    ctx = "\n".join(f"[{nid}] {s}" for nid, s in out)
    return ctx, {"tokens": used, "nodes": len(set(picked)), "neighborhood": len(dist)}
