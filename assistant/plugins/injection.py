"""Heuristic prompt-injection shield for user input AND retrieved chunks (indirect). KPI-03.
Scored rules; block at score >= BLOCK. Heuristic first line of defense — not the only one
(agents are also tool-allowlisted and Tier-3 is HITL gated)."""
from __future__ import annotations
import re
from .base import Stage, RequestContext
from .pii import normalize

# (pattern, weight)
_RULES: list[tuple[re.Pattern, float]] = [(re.compile(p, re.I), w) for p, w in [
    (r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|any|your|the)\b.{0,30}\b(instruction|prompt|rule|direction|guideline|polic|constraint)", 1.0),
    (r"\b(reveal|show|print|repeat|output|leak|display|tell me)\b.{0,40}\b(system|hidden|initial|original|developer)\b.{0,20}\b(prompt|instruction|message|rule)", 1.0),
    (r"\byou are now\b|\bact as\b.{0,30}\b(dan|unrestricted|jailbroken|no (rules|restrictions))|\bdeveloper mode\b|\bDAN\b", 1.0),
    (r"\b(pretend|imagine|roleplay)\b.{0,40}\b(no|without)\b.{0,20}\b(rules|restrictions|filters|guidelines|safety)", 0.8),
    (r"<\s*/?\s*(system|assistant|instructions?)\s*>|\[\s*/?\s*(INST|SYS)\s*\]|<\|im_(start|end)\|>|^\s*system\s*:", 1.0),
    (r"\b(new|updated|real)\s+(instructions?|task|orders?)\s*[:\-]", 0.7),
    (r"\b(do not|don't|never)\b.{0,20}\b(tell|inform|mention|reveal)\b.{0,20}\b(the )?(user|human|operator)", 0.9),
    (r"\b(exfiltrate|send|post|upload|forward)\b.{0,50}\b(to|at)\b.{0,10}https?://", 0.9),
    (r"\b(approve|auto-?approve|skip)\b.{0,30}\b(hitl|approval|review|human)", 1.0),
    (r"\b(as the (admin|administrator|developer|root)|i am (the )?(admin|developer|root))\b.{0,40}\b(allow|enable|disable|grant|override)", 0.8),
    (r"(;|--|/\*)\s*(drop|delete|truncate|update|insert|alter)\b|\bunion\s+select\b|'\s*or\s*'?1'?\s*=\s*'?1", 1.0),
    (r"\b(base64|rot13|hex)\b.{0,30}\b(decode|encoded|instruction)", 0.6),
    (r"\b(forget|ignore|disregard)\b\s+(everything|all)\b.{0,20}\b(above|before|earlier|prior|said)\b|\bobey me\b", 1.0),
    (r"\b(leak|steal|dump|exfiltrate)\b.{0,20}\b(all|the|every)?\s*(data|records|secrets|credentials|passwords)\b", 0.5),
    (r"\bfrom now on\b.{0,40}\b(ignore|you must|always|only)\b", 0.6),
    (r"\b(other|another|different) tenant|^\s*tenant[_ ]?id\s*[=:]\s*\S+", 0.8),
]]
BLOCK = 0.8
_INPUT_ONLY = {len(_RULES) - 1}   # tenant-probing rule: meaningful for user input, noise inside documents (tenancy is structural)


class InjectionShield:
    name = "injection_shield"
    stage = Stage.PRE_EXECUTION
    priority = 20
    fail_closed = True
    enabled = True

    def score(self, text: str) -> tuple[float, list[int]]:
        t = normalize(text)
        hits = [i for i, (rx, _) in enumerate(_RULES) if rx.search(t)]
        s = min(1.0, sum(_RULES[i][1] for i in hits))
        return s, hits

    def scan_chunk(self, chunk_text: str) -> bool:
        """Indirect injection: True if retrieved chunk must be quarantined."""
        t = normalize(chunk_text)
        return min(1.0, sum(w for i, (rx, w) in enumerate(_RULES) if i not in _INPUT_ONLY and rx.search(t))) >= BLOCK

    def run(self, ctx: RequestContext) -> None:
        s, hits = self.score(ctx.text)
        if s >= BLOCK:
            ctx.blocked, ctx.block_reason = True, "prompt_injection"
            ctx.findings.append({"plugin": self.name, "score": s, "rules": hits})
