"""SHA-256 hash-chained, append-only audit log (ADR-011). Payloads must be post-redaction."""
from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass

GENESIS = "0" * 64


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    tenant_id: str
    event_type: str
    payload: dict
    ts: float
    prev_hash: str
    hash: str


class AuditLog:
    def __init__(self, seed: str = "dev-seed"):
        self._seed = seed
        self._events: list[AuditEvent] = []

    def _digest(self, seq, tenant_id, event_type, payload, ts, prev_hash) -> str:
        body = json.dumps(
            {"seq": seq, "tenant_id": tenant_id, "type": event_type, "payload": payload, "ts": ts},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        )
        return hashlib.sha256(f"{self._seed}|{prev_hash}|{body}".encode()).hexdigest()

    def append(self, tenant_id: str, event_type: str, payload: dict, ts: float | None = None) -> AuditEvent:
        ts = time.time() if ts is None else ts
        prev = self._events[-1].hash if self._events else GENESIS
        seq = len(self._events)
        h = self._digest(seq, tenant_id, event_type, payload, ts, prev)
        ev = AuditEvent(seq, tenant_id, event_type, json.loads(json.dumps(payload)), ts, prev, h)
        self._events.append(ev)
        return ev

    def events(self, tenant_id: str | None = None) -> list[AuditEvent]:
        return [e for e in self._events if tenant_id is None or e.tenant_id == tenant_id]

    def verify(self) -> tuple[bool, int | None]:
        prev = GENESIS
        for e in self._events:
            if e.prev_hash != prev or e.hash != self._digest(e.seq, e.tenant_id, e.event_type, e.payload, e.ts, e.prev_hash):
                return False, e.seq
            prev = e.hash
        return True, None
