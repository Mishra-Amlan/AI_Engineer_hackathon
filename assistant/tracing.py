"""W3C TraceContext + lightweight span recorder. Exporter is pluggable (OTLP when the collector is configured)."""
from __future__ import annotations
import re
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

_TP = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def new_traceparent() -> str: return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def parse_traceparent(h: str | None) -> tuple[str, str] | None:
    m = _TP.match(h or "")
    if not m or m.group(1) == "0" * 32 or m.group(2) == "0" * 16: return None
    return m.group(1), m.group(2)


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: str | None
    start: float
    end: float = 0.0
    attrs: dict = field(default_factory=dict)

    @property
    def ms(self) -> float: return (self.end - self.start) * 1000


class Tracer:
    def __init__(self, exporter=None): self.spans: list[Span] = []; self.exporter = exporter

    @contextmanager
    def span(self, name: str, traceparent: str | None = None, parent: Span | None = None, **attrs):
        tp = parse_traceparent(traceparent)
        trace_id = parent.trace_id if parent else (tp[0] if tp else secrets.token_hex(16))
        parent_id = parent.span_id if parent else (tp[1] if tp else None)
        s = Span(name, trace_id, secrets.token_hex(8), parent_id, time.perf_counter(), attrs=dict(attrs))
        try: yield s
        finally:
            s.end = time.perf_counter(); self.spans.append(s)
            if self.exporter:
                try: self.exporter(s)
                except Exception: pass                      # telemetry must never break requests

    @staticmethod
    def header(s: Span) -> str: return f"00-{s.trace_id}-{s.span_id}-01"
