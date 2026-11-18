"""Tenant isolation primitives (ADR-005). Every cache/DB key MUST be built here."""
from __future__ import annotations
import hashlib
import random
import re

_TENANT_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def validate_tenant_id(tenant_id: str) -> str:
    if not isinstance(tenant_id, str) or not _TENANT_RE.fullmatch(tenant_id):
        raise ValueError("invalid tenant_id")
    return tenant_id


def normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def tenant_namespace(tenant_id: str) -> str:
    return f"t:{_h(validate_tenant_id(tenant_id))[:16]}:"


def exact_cache_key(tenant_id: str, user_id: str, query: str) -> str:
    # length-prefix fields so ("a:b","c") can never collide with ("a","b:c")
    material = f"{len(user_id)}:{user_id}|{normalize_query(query)}"
    return f"{tenant_namespace(tenant_id)}q:{_h(material)}"


def jittered_ttl(base: int = 300, jitter: int = 45, rng: random.Random | None = None) -> int:
    r = rng or random
    return base + r.randint(-jitter, jitter)


def assert_key_in_tenant(key: str, tenant_id: str) -> None:
    if not key.startswith(tenant_namespace(tenant_id)):
        raise PermissionError("cross-tenant key access blocked")
