"""Tier-3 HITL gate (KPI-19). Requests are PENDING_APPROVAL until an authorized, different human approves.
State machine: PENDING_APPROVAL -> APPROVED -> APPLIED | REJECTED | EXPIRED. No auto-approve, ever."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from ..audit import AuditLog


@dataclass
class ApprovalRequest:
    id: str
    tenant_id: str
    requester: str
    tool: str
    args: dict
    created: float
    state: str = "PENDING_APPROVAL"
    reviewer: str | None = None
    result: object = None


class HitlError(Exception):
    pass


class HitlQueue:
    def __init__(self, audit: AuditLog, executors: dict[str, Callable[[dict], Awaitable]],
                 clock: Callable[[], float] = time.time, ttl_s: float = 86400):
        self.audit, self.executors, self.clock, self.ttl = audit, executors, clock, ttl_s
        self._reqs: dict[tuple[str, str], ApprovalRequest] = {}

    def submit(self, req: dict) -> ApprovalRequest:           # signature matches ToolHarness.hitl_enqueue
        key = (req["tenant_id"], req["idempotency_key"])
        if key in self._reqs: return self._reqs[key]
        r = ApprovalRequest(req["idempotency_key"], req["tenant_id"], req["user_id"], req["tool"], req["args"], self.clock())
        self._reqs[key] = r
        self.audit.append(r.tenant_id, "hitl.submitted", {"id": r.id, "tool": r.tool, "requester": r.requester})
        return r

    def _get(self, tenant_id: str, rid: str) -> ApprovalRequest:
        r = self._reqs.get((tenant_id, rid))
        if r is None: raise HitlError("not found")           # other tenants' ids look identical to nonexistent
        if r.state == "PENDING_APPROVAL" and self.clock() - r.created > self.ttl:
            r.state = "EXPIRED"; self.audit.append(tenant_id, "hitl.expired", {"id": rid})
        return r

    def list_pending(self, tenant_id: str) -> list[ApprovalRequest]:
        return [r for (t, _), r in self._reqs.items() if t == tenant_id and self._get(t, r.id).state == "PENDING_APPROVAL"]

    def approve(self, tenant_id: str, rid: str, reviewer: str, roles: set[str]) -> ApprovalRequest:
        r = self._get(tenant_id, rid)
        if "approver" not in roles: raise HitlError("reviewer lacks approver role")
        if reviewer == r.requester: raise HitlError("separation of duties: requester cannot approve own request")
        if r.state != "PENDING_APPROVAL": raise HitlError(f"cannot approve in state {r.state}")
        r.state, r.reviewer = "APPROVED", reviewer
        self.audit.append(tenant_id, "hitl.approved", {"id": rid, "reviewer": reviewer})
        return r

    def reject(self, tenant_id: str, rid: str, reviewer: str, roles: set[str]) -> ApprovalRequest:
        r = self._get(tenant_id, rid)
        if "approver" not in roles: raise HitlError("reviewer lacks approver role")
        if r.state != "PENDING_APPROVAL": raise HitlError(f"cannot reject in state {r.state}")
        r.state, r.reviewer = "REJECTED", reviewer
        self.audit.append(tenant_id, "hitl.rejected", {"id": rid, "reviewer": reviewer})
        return r

    async def apply(self, tenant_id: str, rid: str):
        r = self._get(tenant_id, rid)
        if r.state != "APPROVED": raise HitlError(f"cannot apply in state {r.state}")   # also blocks double-apply
        r.state = "APPLYING"                                   # claim before awaiting: concurrent applies cannot both pass
        try:
            r.result = await self.executors[r.tool](r.args)
        except Exception:
            r.state = "APPROVED"; raise
        r.state = "APPLIED"
        self.audit.append(tenant_id, "hitl.applied", {"id": rid, "tool": r.tool})
        return r.result
