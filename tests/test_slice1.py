import random
import pytest
from assistant.audit import AuditLog
from assistant.config import Settings
from assistant.tenancy import (assert_key_in_tenant, exact_cache_key, jittered_ttl,
                               tenant_namespace, validate_tenant_id)


def test_tenant_keys_isolated():
    a = exact_cache_key("tenantA", "u1", "What is the policy?")
    b = exact_cache_key("tenantB", "u1", "What is the policy?")
    assert a != b and a.startswith(tenant_namespace("tenantA"))
    assert exact_cache_key("tenantA", "u1", "  WHAT is   the policy? ") == a  # normalization


def test_no_field_boundary_collision():
    assert exact_cache_key("t", "a:b", "c") != exact_cache_key("t", "a", "b:c")


def test_1000_tenants_no_leaks():
    keys = {exact_cache_key(f"tenant_{i}", "u", "q") for i in range(1000)}
    assert len(keys) == 1000
    for i in range(1000):
        k = exact_cache_key(f"tenant_{i}", "u", "q")
        assert_key_in_tenant(k, f"tenant_{i}")
        with pytest.raises(PermissionError):
            assert_key_in_tenant(k, f"tenant_{i+1}")


@pytest.mark.parametrize("bad", ["", "a b", "t:1", "../x", "x" * 65, "t*"])
def test_bad_tenant_rejected(bad):
    with pytest.raises(ValueError):
        validate_tenant_id(bad)


def test_ttl_jitter_bounds():
    r = random.Random(1)
    ttls = [jittered_ttl(300, 45, r) for _ in range(500)]
    assert min(ttls) >= 255 and max(ttls) <= 345 and len(set(ttls)) > 20


def test_audit_chain_valid_and_tamper_detected():
    log = AuditLog("s")
    for i in range(5):
        log.append("t1", "evt", {"i": i}, ts=float(i))
    assert log.verify() == (True, None)
    object.__setattr__(log._events[2], "payload", {"i": 999})  # tamper
    assert log.verify() == (False, 2)


def test_audit_chain_detects_deletion():
    log = AuditLog("s")
    for i in range(4):
        log.append("t1", "e", {"i": i}, ts=float(i))
    del log._events[1]
    assert log.verify()[0] is False


def test_audit_payload_is_snapshot():
    log = AuditLog()
    p = {"a": 1}
    log.append("t", "e", p)
    p["a"] = 2
    assert log.verify()[0] and log.events()[0].payload == {"a": 1}


def test_settings_load_and_secret_not_leaked():
    env = {"OPENROUTER_API_KEY": "sk-secret-123", "MODEL_T1_PRIMARY": "a", "MODEL_T1_FALLBACK": "b",
           "MODEL_T2_PRIMARY": "c", "MODEL_T2_FALLBACK": "d", "MODEL_T3_PRIMARY": "e",
           "MODEL_T3_FALLBACK": "f", "MODEL_VERIFIER": "g", "DAILY_BUDGET_USD": "1.5"}
    s = Settings.load(env_path="/nonexistent", environ=env)
    assert s.daily_budget_usd == 1.5 and s.model_t2_primary == "c"
    assert "sk-secret-123" not in repr(s) and "sk-secret-123" not in str(s.model_dump())


def test_real_env_file_parses():
    s = Settings.load(".env", environ={})
    assert s.model_t1_primary and s.model_t2_primary and s.model_verifier
    assert s.openrouter_api_key.get_secret_value() != ""
