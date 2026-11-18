---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0034
domain: engineering
risk_tier: 1
version: v1
---
# Gate 17: Token Optimization using Obsidian & Graphify

Eliminate prompt bloat and reduce LLM input token volume by 45–65% while lowering TTFT: 1. Atomic Obsidian Knowledge Vault: Convert all enterprise policies, SOPs, and product catalogs into atomic Markdown notes stored in `knowledge_vault/`. Each note contains strict YAML frontmatter (`id`, `domain`, `risk_tier`, `version`) and explicit `[[wikilinks]]` to related rules. 2. Graphify Topology Subgraph Pruning: Execute `graphify build ./src ./knowledge_vault --output graph.json` to generate a unified structural dependency graph of Python modules, Pydantic schemas, and Obsidian policy nodes. At runtime, `mcp-graphify-vault` resolves the exact query anchor node and traverses at most `depth=2` edges, injecting only the minimal connected subgraph (~320 tokens vs. ~1,400 tokens raw chunk dump).

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0033]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0035]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0015]]
