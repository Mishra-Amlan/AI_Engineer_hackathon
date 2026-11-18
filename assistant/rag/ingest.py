"""Ingestion Agent (offline): docx -> structured blocks -> 512-token chunks w/ 64 overlap.
Tables are linearized row-by-row ("col: value") so a row is never split from its headers.
Chunks carry tenant_id, source, section, version and a content hash (dedup)."""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from ..plugins.pii import normalize


@dataclass(frozen=True)
class Chunk:
    id: str
    tenant_id: str
    source: str
    section: str
    text: str
    chunk_hash: str
    version: str = "v1"


def iter_blocks(path: Path):
    doc = Document(str(path))
    for el in doc.element.body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "p":
            p = Paragraph(el, doc)
            t = p.text.strip()
            if t:
                yield ("heading" if p.style.name.lower().startswith(("heading", "title")) or _looks_heading(t) else "para", t)
        elif tag == "tbl":
            tbl = Table(el, doc)
            rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in tbl.rows]
            if len(rows) > 1:
                hdr = rows[0]
                for r in rows[1:]:
                    yield ("row", "; ".join(f"{h}: {v}" for h, v in zip(hdr, r) if v))
            elif rows:
                yield ("para", " | ".join(rows[0]))


def _looks_heading(t: str) -> bool:
    return bool(re.match(r"^(Gate \d|\d+\.\s|\d+\.\d+\s|Step \d+|[A-Z]\.\s)", t)) and len(t) < 140


def _approx_split(text: str, tok, max_tok: int, overlap: int) -> list[str]:
    ids = tok.encode(text, add_special_tokens=False)
    if len(ids) <= max_tok:
        return [text]
    out, step = [], max_tok - overlap
    for i in range(0, len(ids), step):
        out.append(tok.decode(ids[i:i + max_tok]))
        if i + max_tok >= len(ids):
            break
    return out


def chunk_document(path: Path, tenant_id: str, tokenizer, max_tok: int = 512, overlap: int = 64,
                   target_tok: int = 220) -> list[Chunk]:
    """Pack consecutive blocks under a heading into ~target_tok chunks (keeps clauses together),
    hard-capped at max_tok with overlap for oversize blocks."""
    source, section, buf, chunks, seen = path.stem, "", [], [], set()

    def flush():
        nonlocal buf
        if not buf:
            return
        body = " ".join(buf)
        for piece in _approx_split(body, tokenizer, max_tok, overlap):
            text = normalize(f"[{source} > {section}] {piece}" if section else f"[{source}] {piece}")
            h = hashlib.sha256(text.encode()).hexdigest()[:16]
            if h in seen:
                continue
            seen.add(h)
            chunks.append(Chunk(id=f"{source}#{len(chunks):04d}", tenant_id=tenant_id, source=source,
                                section=section, text=text, chunk_hash=h))
        buf = []

    cur = 0
    for kind, text in iter_blocks(path):
        if kind == "heading":
            flush(); cur = 0; section = text[:120]; continue
        n = len(tokenizer.encode(text, add_special_tokens=False))
        if cur + n > target_tok and buf:
            flush(); cur = 0
        buf.append(text); cur += n
    flush()
    return chunks
