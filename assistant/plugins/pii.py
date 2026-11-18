"""Deterministic PII redactor (KPI-02). Normalizes unicode, de-obfuscates, then redacts."""
from __future__ import annotations
import re
import unicodedata
from .base import Stage, RequestContext

_ZW = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
# common cross-script homoglyphs (Cyrillic/Greek lookalikes -> latin)
_HOMO = str.maketrans({"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
                       "і": "i", "ѕ": "s", "ԁ": "d", "ο": "o", "ν": "v", "Α": "A", "Ε": "E"})

def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_ZW).translate(_HOMO)
    return t

_AT = r"(?:@|\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\}|\s+at\s+)"
_DOT = r"(?:\.|\[\s*dot\s*\]|\(\s*dot\s*\)|\{\s*dot\s*\}|\s+dot\s+)"
_EMAIL = re.compile(rf"[A-Za-z0-9._%+\-]+\s*{_AT}\s*[A-Za-z0-9\-]+(?:\s*{_DOT}\s*[A-Za-z0-9\-]+)+", re.I)
_SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}[-\s.]?(?!00)\d{2}[-\s.]?(?!0000)\d{4}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ \-]?){13,19}(?!\d)")


def _luhn(num: str) -> bool:
    d = [int(c) for c in num][::-1]
    s = sum(d[0::2]) + sum(sum(divmod(x * 2, 10)) for x in d[1::2])
    return s % 10 == 0


class PiiRedactor:
    name = "pii_redactor"
    stage = Stage.PRE_EXECUTION
    priority = 10
    fail_closed = True
    enabled = True

    def redact(self, text: str) -> tuple[str, dict[str, int]]:
        counts: dict[str, int] = {}
        t = normalize(text)

        def sub(rx, label, s, check=None):
            def r(m):
                if check and not check(m.group(0)):
                    return m.group(0)
                counts[label] = counts.get(label, 0) + 1
                return f"[{label}]"
            return rx.sub(r, s)

        t = sub(_EMAIL, "EMAIL", t)
        t = sub(_CARD, "CARD", t, lambda s: 13 <= len(re.sub(r"\D", "", s)) <= 19 and _luhn(re.sub(r"\D", "", s)))
        t = sub(_SSN, "SSN", t)
        t = sub(_PHONE, "PHONE", t)
        return t, counts

    def run(self, ctx: RequestContext) -> None:
        ctx.text, counts = self.redact(ctx.text)
        if counts:
            ctx.findings.append({"plugin": self.name, "redactions": counts})  # counts only, no values
