"""Gate 2 artifact: docs/workflow_orchestration.png (300 DPI). matplotlib fallback (no Graphviz `dot` on this host)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(16, 9)); ax.set_xlim(0, 160); ax.set_ylim(0, 90); ax.axis("off")
pos = {}
def box(key, x, y, w, h, text, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=color, ec="#333", lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.5, wrap=True); pos[key] = (x, y, w, h)
def arrow(a, b, label=""):
    ax0, ay0, aw, ah = pos[a]; bx0, by0, bw, bh = pos[b]
    p0 = (ax0 + aw, ay0 + ah / 2) if bx0 > ax0 + aw - 1 else (ax0 + aw / 2, ay0 if by0 < ay0 else ay0 + ah)
    p1 = (bx0, by0 + bh / 2) if bx0 > ax0 + aw - 1 else (bx0 + bw / 2, by0 + bh if by0 < ay0 else by0)
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="->", lw=1.1, color="#444"))
    if label: ax.text((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + 1.2, label, fontsize=6.5, ha="center", color="#a00")
for x, t in [(1, "INGRESS & SECURITY"), (41, "TRIAGE & SUBAGENT ROUTING"), (81, "MCP & 3-STAGE RAG"), (121, "CONTROL PLANE & EGRESS")]:
    ax.add_patch(FancyBboxPatch((x, 3), 38, 82, boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#999", lw=0.8, ls="--")); ax.text(x + 19, 87, t, ha="center", fontsize=9, weight="bold")
box("in", 4, 70, 32, 8, "Client → API Gateway\nFastAPI (tenant header bound)", "#dbeafe")
box("pii", 4, 55, 32, 8, "Pre-Hook 1: PII Redactor\n(fail-closed)", "#fde68a")
box("inj", 4, 40, 32, 8, "Pre-Hook 2: Injection Shield\n(fail-closed)", "#fde68a")
box("cache", 4, 25, 32, 8, "Redis Semantic Cache\n(tenant namespace, cosine ≥ .92)", "#d1fae5")
box("tri", 44, 66, 32, 10, "Triage Agent (T=0, ≤25 ms)\nintent·domain·risk·complexity", "#c7d2fe")
box("dir", 44, 50, 32, 7, "Direct / canned (T0)", "#e5e7eb")
box("ret", 44, 38, 32, 8, "Retrieval Subagent (read-only)", "#bbf7d0")
box("exe", 44, 26, 32, 8, "Execution Subagent\n(state-store only)", "#fecaca")
box("ver", 44, 12, 32, 8, "Verification Subagent\n(independent model, veto)", "#fbcfe8")
box("rag", 84, 62, 32, 18, "mcp-hybrid-rag\nBM25 (k1=1.25,b=.75) + Bi-Encoder HNSW\n→ RRF (k=60, pool 40)\n→ Cross-Encoder (thr 0.42, top 4)", "#bbf7d0")
box("gr", 84, 42, 32, 9, "mcp-graphify-vault\nObsidian notes, depth ≤ 2", "#bbf7d0")
box("st", 84, 26, 32, 9, "mcp-state-store\nPostgres + tenant Redis", "#bbf7d0")
box("rt", 84, 8, 32, 12, "Model Router (T0–T3)\nretry→fallback→lower tier\n→extractive→abstain", "#ddd6fe")
box("rx", 124, 66, 32, 10, "Bounded ReAct loop\nmax 5 steps · GoalAnchor idx 0", "#fed7aa")
box("cb", 124, 52, 32, 8, "Idempotent Circuit Breaker\n(2 identical failures → HALT)", "#fed7aa")
box("hitl", 124, 38, 32, 8, "Tier-3 HITL Gate\nPENDING_APPROVAL (human)", "#fecaca")
box("post", 124, 22, 32, 10, "Post-Hook: RAGAS audit\nOTel export (W3C traceparent)", "#e5e7eb")
box("out", 124, 8, 32, 8, "Response + citations", "#dbeafe")
for a, b, l in [("in", "pii", ""), ("pii", "inj", ""), ("inj", "cache", ""), ("cache", "tri", "miss"), ("ret", "rag", "JSON-RPC"), ("ret", "gr", ""), ("exe", "st", ""), ("ver", "rt", ""),
                ("exe", "rx", ""), ("rx", "cb", ""), ("cb", "hitl", ""), ("hitl", "post", ""), ("post", "out", "")]:
    arrow(a, b, l)
# triage routing bus (left gutter) so arrows never cross other boxes
ax.plot([42.3, 42.3], [71, 22], color="#444", lw=1.1)
ax.plot([42.3, 44], [71, 71], color="#444", lw=1.1)
for key, label in (("dir", "DIRECT / OOS"), ("ret", "HYBRID_RAG"), ("exe", "TRANSACTION")):
    x, y, w, h = pos[key]; ax.annotate("", xy=(x, y + h / 2), xytext=(42.3, y + h / 2), arrowprops=dict(arrowstyle="->", lw=1.1, color="#444"))
    ax.text(40.8, y + h / 2 + 1.2, label, fontsize=5.8, ha="right", color="#a00")
x, y, w, h = pos["ret"]; vx, vy, vw, vh = pos["ver"]
ax.annotate("draft answer", xy=(vx + vw / 2, vy + vh), xytext=(x + w / 2, y), arrowprops=dict(arrowstyle="->", lw=1.1, color="#444", connectionstyle="arc3,rad=0"), fontsize=6, color="#a00", ha="left")
ax.set_title("The Unreliable Assistant — Workflow Orchestration (Gate 2)", fontsize=12, weight="bold")
fig.savefig("docs/workflow_orchestration.png", dpi=300, bbox_inches="tight"); print("saved")
