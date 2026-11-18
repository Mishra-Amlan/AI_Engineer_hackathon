"""ToolExecutionHarness (Gate 4): repair -> strict validation -> RBAC tier -> idempotency -> breaker -> run.
Tier-3 handlers are NEVER invoked here: the harness records a PENDING_APPROVAL request (HITL, slice 6)."""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable
from pydantic import BaseModel, ValidationError


class Tier(IntEnum):
    TIER_1_READ = 1
    TIER_2_COMPUTE = 2
    TIER_3_MUTATE = 3


_SKU = re.compile(r"^\s*sku[\s_-]?(\d{1,3})\s*$", re.I)
_LOT = re.compile(r"^\s*lot[\s_-]?(\d{1,5})\s*$", re.I)


def repair_value(v: str) -> tuple[str, bool]:
    if (m := _SKU.match(v)): return f"SKU-{int(m.group(1)):03d}", True
    if (m := _LOT.match(v)): return f"LOT-{int(m.group(1)):05d}", True
    return v, False


def repair_args(args: dict) -> tuple[dict, list[str]]:
    out, fixed = {}, []
    for k, v in args.items():
        if isinstance(v, str):
            nv, ch = repair_value(v); out[k] = nv
            if ch: fixed.append(k)
        elif isinstance(v, list):
            items = [repair_value(x) if isinstance(x, str) else (x, False) for x in v]
            out[k] = [i[0] for i in items]
            if any(i[1] for i in items): fixed.append(k)
        else:
            out[k] = v
    return out, fixed


def args_hash(tool: str, args: dict) -> str:
    return hashlib.sha256((tool + json.dumps(args, sort_keys=True, default=str)).encode()).hexdigest()[:16]


@dataclass
class ToolSpec:
    name: str
    tier: Tier
    model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[Any]]
    timeout_s: float | None = None      # per-tool override of the harness step timeout (e.g. retrieval on slow CPU in dev)


@dataclass
class ToolResult:
    ok: bool
    status: str                 # OK | PENDING_APPROVAL | ERROR | HALTED_BREAKER | REPLAY
    data: Any = None
    error_code: str = ""
    message: str = ""
    remediation: str = ""
    repaired: list[str] = field(default_factory=list)
    first_pass_valid: bool = True


@dataclass
class Principal:
    tenant_id: str
    user_id: str
    max_tier: Tier = Tier.TIER_2_COMPUTE     # callers get T3 *requests*, never direct T3 execution
    allowed_tools: frozenset[str] | None = None   # per-agent allowlist, enforced here (not in prompts)


class ToolHarness:
    def __init__(self, tools: list[ToolSpec], breaker_threshold: int = 2, step_timeout_s: float = 0.12,
                 hitl_enqueue: Callable[[dict], None] | None = None):
        self.tools = {t.name: t for t in tools}
        self.threshold, self.timeout = breaker_threshold, step_timeout_s
        self.fail_counts: dict[tuple[str, str], int] = {}
        self.idem: dict[tuple[str, str], ToolResult] = {}
        self.pending: list[dict] = []
        self.hitl_enqueue = hitl_enqueue or self.pending.append
        self.stats = {"calls": 0, "first_pass_valid": 0, "repaired_ok": 0, "repair_needed": 0}

    def _err(self, code, msg, remedy, **kw) -> ToolResult:
        return ToolResult(False, "ERROR", error_code=code, message=msg, remediation=remedy, **kw)

    async def execute(self, tool: str, args: dict, who: Principal, idempotency_key: str | None = None) -> ToolResult:
        if who.allowed_tools is not None and tool not in who.allowed_tools:
            return self._err("E_FORBIDDEN", f"tool '{tool}' not in this agent's allowlist", "use an allowed tool")
        spec = self.tools.get(tool)
        if spec is None:
            return self._err("E_UNKNOWN_TOOL", f"unknown tool '{tool}'", "use an allowed tool")
        self.stats["calls"] += 1
        # 1. strict validation first; 2. deterministic repair only if it failed
        first_pass = True
        try:
            parsed = spec.model.model_validate(args, strict=True); fixed = []
        except ValidationError:
            first_pass = False
            rargs, fixed = repair_args(args)
            self.stats["repair_needed"] += 1
            try:
                parsed = spec.model.model_validate(rargs, strict=True); args = rargs
                self.stats["repaired_ok"] += 1
            except ValidationError as e:
                key = (tool, args_hash(tool, args))
                self.fail_counts[key] = self.fail_counts.get(key, 0) + 1
                if self.fail_counts[key] >= self.threshold:
                    return ToolResult(False, "HALTED_BREAKER", error_code="E_BREAKER", first_pass_valid=False,
                                      message=f"{tool} failed {self.fail_counts[key]}x with identical arguments",
                                      remediation="Check the identifier format (e.g. SKU-099, LOT-00044) and rephrase the request.")
                return self._err("E_SCHEMA", f"invalid arguments: {e.errors()[0]['loc']}", "fix the arguments", first_pass_valid=False)
        if first_pass: self.stats["first_pass_valid"] += 1
        key = (tool, args_hash(tool, args))
        if self.fail_counts.get(key, 0) >= self.threshold:
            return ToolResult(False, "HALTED_BREAKER", error_code="E_BREAKER", message="breaker open for identical call",
                              remediation="Change the arguments or ask a human operator.")
        # 3. RBAC: T3 is always a HITL request, never executed here
        if spec.tier == Tier.TIER_3_MUTATE:
            if not idempotency_key or not _is_uuid4(idempotency_key):
                return self._err("E_IDEMPOTENCY", "Tier-3 call requires a UUIDv4 idempotency_key", "supply uuid4")
            ik = (who.tenant_id, idempotency_key)
            if ik in self.idem:
                r = self.idem[ik]; return ToolResult(r.ok, "REPLAY", data=r.data, repaired=r.repaired)
            req = {"tenant_id": who.tenant_id, "user_id": who.user_id, "tool": tool,
                   "args": parsed.model_dump(), "idempotency_key": idempotency_key, "state": "PENDING_APPROVAL"}
            self.hitl_enqueue(req)
            res = ToolResult(True, "PENDING_APPROVAL", data={"idempotency_key": idempotency_key}, repaired=fixed, first_pass_valid=first_pass)
            self.idem[ik] = res
            return res
        if spec.tier > who.max_tier:
            return self._err("E_FORBIDDEN", f"tier {spec.tier.name} not permitted", "request approval")
        # 4. run with per-step timeout
        try:
            data = await asyncio.wait_for(spec.handler(parsed), spec.timeout_s or self.timeout)
            return ToolResult(True, "OK", data=data, repaired=fixed, first_pass_valid=first_pass)
        except asyncio.TimeoutError:
            self.fail_counts[key] = self.fail_counts.get(key, 0) + 1
            return self._err("E_TIMEOUT", f"{tool} exceeded {self.timeout*1000:.0f} ms", "retry later", repaired=fixed)
        except Exception as e:  # noqa: BLE001
            self.fail_counts[key] = self.fail_counts.get(key, 0) + 1
            return self._err("E_TOOL", type(e).__name__, "check arguments", repaired=fixed)


def _is_uuid4(s: str) -> bool:
    try: return uuid.UUID(s).version == 4
    except (ValueError, AttributeError): return False
