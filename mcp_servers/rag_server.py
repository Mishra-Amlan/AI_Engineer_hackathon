"""MCP server `hybrid-rag` (stdio). Tool: hybrid_retrieve. Read-only (TIER_1_READ).
Run: uv run mcp_servers/rag_server.py   (loads data/chunks.jsonl; models from .env/defaults)"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from assistant.rag.ingest import Chunk
from assistant.rag.retriever import HybridRetriever
from assistant.tenancy import validate_tenant_id


class RetrieveIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tenant_id: str
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=50)


def retrieve_tool(r: HybridRetriever, args: dict) -> dict:
    a = RetrieveIn(**args)
    validate_tenant_id(a.tenant_id)
    try:
        res = r.retrieve(a.tenant_id, a.query)
    except PermissionError:
        return {"error": {"code": "E_NOT_FOUND", "message": "unknown tenant", "retryable": False, "remediation": "check tenant"}}
    return {"chunks": [{"id": h.chunk.id, "text": h.chunk.text, "score": h.rerank, "source": h.chunk.source}
                       for h in res.hits[:a.top_k]],
            "confidence": res.confidence, "abstain": res.abstain, "degraded": res.degraded, "low_confidence": res.low_confidence,
            "timings_ms": res.timings_ms}


def build_retriever() -> HybridRetriever:
    from sentence_transformers import CrossEncoder, SentenceTransformer
    chunks = [Chunk(**json.loads(l)) for l in open("data/chunks.jsonl")]
    return HybridRetriever(chunks, SentenceTransformer(os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")),
                           CrossEncoder(os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")))


if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP
    mcp, retriever = FastMCP("hybrid-rag"), build_retriever()

    @mcp.tool()
    def hybrid_retrieve(tenant_id: str, query: str, top_k: int = 4) -> str:
        """3-stage hybrid retrieval (BM25 + dense -> RRF -> cross-encoder). Read-only."""
        return json.dumps(retrieve_tool(retriever, {"tenant_id": tenant_id, "query": query, "top_k": top_k}))

    mcp.run(transport="stdio")
