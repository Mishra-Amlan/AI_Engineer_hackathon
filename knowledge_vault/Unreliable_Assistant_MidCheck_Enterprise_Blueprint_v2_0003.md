---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0003
domain: engineering
risk_tier: 3
version: v1
---
# Gate 0: Enterprise Stack, MCP Servers & Plugin Architecture

Layer / Capability: Token Compression; Selected Tool / Protocol: Obsidian Vault + Graphify AST/Link Engine; MCP Server / Plugin Binding: MCP Server: `mcp-graphify-vault`; Architectural Justification: Traverses 1-hop/2-hop `[[wikilinks]]` and code dependency graphs to cut tokens 55%. Layer / Capability: Lifecycle Plugins; Selected Tool / Protocol: Pluggy / Entry-Point Hook Registry; MCP Server / Plugin Binding: Pre-Hook, Post-Hook, PII, OTel, HITL Plugins; Architectural Justification: Hot-swappable deterministic interceptors decoupled from core LLM reasoning. MCP Configuration & Plugin Registration Blueprint (`mcp_config.json`)

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0002]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0004]]
