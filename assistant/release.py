"""Versioned artifacts, feature flags with kill switches, and canary rollout with auto-rollback (CLAUDE.md §10)."""
from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Callable

GUARDRAILS_ALWAYS_ON = {"pii_redactor", "injection_shield"}     # fail-closed plugins: flags cannot disable them


@dataclass(frozen=True)
class ArtifactVersion:
    name: str
    version: str
    content: dict
    digest: str


class ArtifactRegistry:
    """Immutable versions of prompts / router policy / thresholds / index alias. activate() and rollback() are O(1) pointer flips."""
    def __init__(self):
        self._v: dict[str, dict[str, ArtifactVersion]] = {}
        self._active: dict[str, list[str]] = {}               # history stack of active versions

    def register(self, name: str, version: str, content: dict) -> ArtifactVersion:
        if version in self._v.get(name, {}): raise ValueError("versions are immutable")
        d = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:12]
        av = ArtifactVersion(name, version, json.loads(json.dumps(content)), d)
        self._v.setdefault(name, {})[version] = av
        return av

    def activate(self, name: str, version: str) -> None:
        if version not in self._v.get(name, {}): raise KeyError(version)
        self._active.setdefault(name, []).append(version)

    def rollback(self, name: str) -> str:
        h = self._active.get(name, [])
        if len(h) < 2: raise RuntimeError("no previous version")
        h.pop(); return h[-1]

    def active(self, name: str) -> ArtifactVersion:
        return self._v[name][self._active[name][-1]]

    def snapshot(self) -> dict[str, str]:                      # attached to every trace/audit event
        return {n: f"{h[-1]}@{self._v[n][h[-1]].digest}" for n, h in self._active.items() if h}


class FlagService:
    def __init__(self, fetch: Callable[[], dict] | None = None):
        self._fetch, self._lkg = fetch, {}                     # last-known-good cache survives backend outages
        self.local: dict[str, dict] = {}

    def set(self, name: str, enabled: bool = True, percent: int = 100) -> None:
        if name in GUARDRAILS_ALWAYS_ON and not enabled: raise PermissionError(f"'{name}' is a fail-closed guardrail")
        self.local[name] = {"enabled": enabled, "percent": percent}

    def _flags(self) -> dict:
        try:
            if self._fetch: self._lkg = self._fetch()
            else: self._lkg = dict(self.local)
        except Exception:  # noqa: BLE001 — flag backend down: use last-known-good
            pass
        return self._lkg

    def is_on(self, name: str, tenant_id: str, default: bool = False) -> bool:
        if name in GUARDRAILS_ALWAYS_ON: return True           # fail-safe: guardrails never depend on the flag backend
        f = self._flags().get(name)
        if f is None: return default
        if not f["enabled"]: return False
        b = int(hashlib.sha256(f"{name}:{tenant_id}".encode()).hexdigest()[:8], 16) % 100   # sticky per-tenant bucket
        return b < f["percent"]


@dataclass
class Guardrails:
    p95_ms: float = 550
    faithfulness: float = 0.90
    err_5xx: float = 0.0005
    cross_tenant_leaks: int = 0
    hitl_bypass: int = 0

    def breaches(self, m: dict) -> list[str]:
        out = []
        if m.get("p95_ms", 0) > self.p95_ms: out.append("p95_ms")
        if m.get("faithfulness", 1) < self.faithfulness: out.append("faithfulness")
        if m.get("err_5xx", 0) > self.err_5xx: out.append("err_5xx")
        if m.get("cross_tenant_leaks", 0) > self.cross_tenant_leaks: out.append("cross_tenant_leaks")
        if m.get("hitl_bypass", 0) > self.hitl_bypass: out.append("hitl_bypass")
        return out


@dataclass
class RolloutResult:
    final_percent: int
    rolled_back: bool
    breaches: list[str] = field(default_factory=list)
    history: list[tuple[int, str]] = field(default_factory=list)
    rollback_seconds: float = 0.0


class RolloutController:
    STAGES = (1, 5, 25, 100)

    def __init__(self, flags: FlagService, registry: ArtifactRegistry, guard: Guardrails | None = None, on_rollback: Callable[[], None] | None = None):
        self.flags, self.reg, self.guard, self.on_rollback = flags, registry, guard or Guardrails(), on_rollback

    def rollout(self, flag: str, artifact: str, new_version: str, measure: Callable[[int], dict]) -> RolloutResult:
        """measure(percent) -> metrics observed while the candidate serves `percent` of tenants."""
        self.reg.activate(artifact, new_version); res = RolloutResult(0, False)
        for pct in self.STAGES:
            self.flags.set(flag, True, pct); res.final_percent = pct
            b = self.guard.breaches(measure(pct)); res.history.append((pct, "ok" if not b else "BREACH:" + ",".join(b)))
            if b:
                t = time.perf_counter()
                self.flags.set(flag, False, 0); self.reg.rollback(artifact)
                if self.on_rollback: self.on_rollback()
                res.rolled_back, res.breaches, res.final_percent = True, b, 0
                res.rollback_seconds = time.perf_counter() - t
                return res
        return res
