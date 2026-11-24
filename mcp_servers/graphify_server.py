"""MCP server `graphify-vault` (stdio). Tool: graph_subgraph. Read-only. depth is hard-capped at 2."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from assistant.graphify import Graph, count_tokens, prune_context


class SubgraphIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tenant_id: str
    query: str = Field(min_length=1, max_length=2000)
    anchors: list[str] = Field(min_length=1, max_length=8)
    depth: int = Field(default=2, ge=1, le=2)
    budget: int = Field(default=320, ge=50, le=1000)


def subgraph_tool(graph: Graph, tokenizer, args: dict) -> dict:
    a = SubgraphIn(**args)
    anchors = [x for x in a.anchors if x in graph.nodes]
    if not anchors:
        return {"error": {"code": "E_NO_ANCHOR", "message": "no known anchor", "retryable": False, "remediation": "pass chunk ids from hybrid_retrieve"}}
    ctx, info = prune_context(graph, a.query, anchors, tokenizer, a.depth, a.budget)
    return {"context": ctx, **info}


if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP
    from transformers import AutoTokenizer
    mcp, g, tok = FastMCP("graphify-vault"), Graph(), AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")

    @mcp.tool()
    def graph_subgraph(tenant_id: str, query: str, anchors: list[str], depth: int = 2, budget: int = 320) -> str:
        """Depth<=2 pruned context from the Obsidian/Graphify graph. Read-only."""
        return json.dumps(subgraph_tool(g, tok, {"tenant_id": tenant_id, "query": query, "anchors": anchors, "depth": depth, "budget": budget}))

    mcp.run(transport="stdio")
