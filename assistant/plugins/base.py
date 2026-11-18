"""Lifecycle plugin framework: ordered, stage-scoped, fail-closed interceptors."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Stage(str, Enum):
    PRE_EXECUTION = "PRE_EXECUTION"
    TOOL_DISPATCH = "TOOL_DISPATCH"
    POST_EXECUTION = "POST_EXECUTION"


@dataclass
class RequestContext:
    tenant_id: str
    user_id: str
    text: str                        # working text (progressively sanitized)
    request_id: str = ""
    blocked: bool = False
    block_reason: str = ""
    findings: list[dict] = field(default_factory=list)   # never contains raw PII
    timings_ms: dict[str, float] = field(default_factory=dict)


class Plugin(Protocol):
    name: str
    stage: Stage
    priority: int
    fail_closed: bool
    enabled: bool
    def run(self, ctx: RequestContext) -> None: ...


class PluginManager:
    def __init__(self, plugins: list[Plugin] | None = None):
        self._plugins: list[Plugin] = list(plugins or [])

    def register(self, p: Plugin) -> None:
        self._plugins.append(p)

    def set_enabled(self, name: str, enabled: bool) -> None:
        for p in self._plugins:
            if p.name == name:
                if p.fail_closed and not enabled:
                    raise PermissionError(f"fail-closed plugin '{name}' cannot be disabled")
                p.enabled = enabled
                return
        raise KeyError(name)

    def run_stage(self, stage: Stage, ctx: RequestContext) -> RequestContext:
        for p in sorted((p for p in self._plugins if p.stage == stage), key=lambda p: p.priority):
            if not p.enabled or ctx.blocked:
                continue
            t0 = time.perf_counter()
            try:
                p.run(ctx)
            except Exception as e:  # noqa: BLE001
                if p.fail_closed:
                    ctx.blocked, ctx.block_reason = True, f"plugin_error:{p.name}"
                    ctx.findings.append({"plugin": p.name, "error": type(e).__name__})
                else:
                    ctx.findings.append({"plugin": p.name, "error_ignored": type(e).__name__})
            finally:
                ctx.timings_ms[p.name] = (time.perf_counter() - t0) * 1000
        return ctx
