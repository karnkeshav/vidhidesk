"""Tests for the organization-level access gate (app/auth.py::
_check_organization_access), added 27 Aug 2026 as a second, ADDITIVE gate
alongside (never replacing) the existing per-user account_security trial
check. Exercises the REAL get_current_user() end to end (real ES256 JWTs,
same pattern as test_auth.py) with app.auth.service_client mocked to a
fake table backend -- proving both individual behaviors and, critically,
the PRECEDENCE between the two checks (account_security first).

Also covers deterministic organization resolution (memberships.is_default)
and the write-then-read integration between the Platform Owner Dashboard's
access-update endpoint and this gate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import jwks_client

from tests._es256_helpers import (
    DEFAULT_KID,
    TEST_SUPABASE_URL,
    generate_keypair,
    jwks_body,
    make_token,
)
from tests.test_platform import FakeServiceClient, _org

from app import auth as auth_module
from app.auth import CurrentUser, get_current_user
from app.routers import platform as platform_module
from app.models.schemas import OrganizationAccessUpdate


@pytest.fixture(autouse=True)
def _mock_env_and_caches(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-anon-key")
    get_settings.cache_clear()
    jwks_client.cache_clear()
    # Every fetch function in auth.py keeps a module-level TTL cache
    # (_account_lock_cache / _org_id_cache / _org_access_cache). Tests in
    # this file reuse fixed user/org ids across test functions for
    # readability -- without clearing these between tests, an earlier
    # test's cached state would silently leak into a later one and mask
    # a real regression instead of catching it.
    auth_module._account_lock_cache.clear()
    auth_module._org_id_cache.clear()
    auth_module._org_access_cache.clear()
    yield
    auth_module._account_lock_cache.clear()
    auth_module._org_id_cache.clear()
    auth_module._org_access_cache.clear()
    jwks_client.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def keypair():
    return generate_keypair()


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch, keypair):
    _, pub = keypair
    body = jwks_body((pub, DEFAULT_KID))

    def fetch_data(self):
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(body)
        return body

    monkeypatch.setattr(pyjwt.PyJWKClient, "fetch_data", fetch_data)


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user: CurrentUser = Depends(get_current_user)):
        return {"id": user.id, "organization_id": user.organization_id}

    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


def _token(keypair, user_id: str, **overrides) -> str:
    priv, _ = keypair
    return make_token(priv, sub=user_id, email=f"{user_id}@example.com", **overrides)


def _account_row(user_id: str, *, login_started_at: datetime, payment_received: bool = False) -> dict:
    return {
        "user_id": user_id,
        "login_started_at": login_started_at.isoformat(),
        "payment_received": payment_received,
    }


def _membership_row(user_id: str, org_id: str, is_default: bool = True) -> dict:
    return {"user_id": user_id, "organization_id": org_id, "is_default": is_default}


def _seed(monkeypatch, *, account_rows=(), membership_rows=(), org_rows=()):
    fake = FakeServiceClient(
        {
            "account_security": list(account_rows),
            "memberships": list(membership_rows),
            "organizations": list(org_rows),
            "organization_access_events": [],
        }
    )
    monkeypatch.setattr(auth_module, "service_client", lambda: fake)
    return fake


NOW = datetime.now(timezone.utc)


# --- 1-3: organization gate behaviors -------------------------------------


def test_valid_account_and_enabled_org_allows_access(monkeypatch, client, keypair):
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="active")],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["organization_id"] == "org-1"


def test_suspended_organization_denies_with_org_access_disabled(monkeypatch, client, keypair):
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="suspended")],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "ORG_ACCESS_DISABLED" in res.json()["detail"]


def test_access_disabled_organization_denies_even_if_status_active(monkeypatch, client, keypair):
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="active", access_enabled=False)],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "ORG_ACCESS_DISABLED" in res.json()["detail"]


# --- 4-5: precedence with the existing trial check -------------------------


def test_expired_trial_with_enabled_org_still_trial_expired(monkeypatch, client, keypair):
    """Existing TRIAL_EXPIRED behavior must be byte-for-byte preserved."""
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW - timedelta(days=6))],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="active")],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "TRIAL_EXPIRED" in res.json()["detail"]


def test_expired_trial_and_suspended_org_precedence_is_trial_expired(monkeypatch, client, keypair):
    """account_security is checked FIRST -- an expired trial must surface
    as TRIAL_EXPIRED even when the organization is ALSO suspended, proving
    the organization gate never even runs in this case (existing semantics
    preserved exactly)."""
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW - timedelta(days=6))],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="suspended")],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "TRIAL_EXPIRED" in res.json()["detail"]
    assert "ORG_ACCESS_DISABLED" not in res.json()["detail"]


def test_payment_received_bypasses_trial_but_not_org_suspension(monkeypatch, client, keypair):
    """payment_received is a USER-level bypass only -- it must not also
    bypass an organization-level suspension. These are independent gates."""
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW - timedelta(days=6), payment_received=True)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="suspended")],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "ORG_ACCESS_DISABLED" in res.json()["detail"]


def test_missing_organization_membership_is_denied(monkeypatch, client, keypair):
    """Round 2 of the security review (27 Aug 2026): the first version of
    this gate treated 'no membership row at all' as an implicit allow
    (fail open). That was removed -- no valid default organization
    membership must deny with a clear, machine-readable 403, distinct
    from both TRIAL_EXPIRED and ORG_ACCESS_DISABLED."""
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[],
        org_rows=[],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "ORG_MEMBERSHIP_REQUIRED" in res.json()["detail"]


def test_membership_referencing_nonexistent_organization_is_denied(monkeypatch, client, keypair):
    """A membership row exists (organization_id resolves) but the
    organization row itself doesn't -- a data-integrity edge case that
    must still deny, never fall through as an allow."""
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-does-not-exist")],
        org_rows=[],  # no organizations row at all
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "ORG_MEMBERSHIP_REQUIRED" in res.json()["detail"]


# --- 6-8: owner dashboard actions have real, observable effect -------------


def _owner_user() -> CurrentUser:
    return CurrentUser(id="owner-1", email="keshav.karn@gmail.com", db=None)


def test_owner_suspend_then_protected_request_is_denied(monkeypatch, client, keypair):
    fake = _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="active")],
    )
    monkeypatch.setattr(platform_module, "service_client", lambda: fake)

    token = _token(keypair, "user-1")
    assert client.get("/whoami", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    platform_module.update_organization_access(
        "org-1", OrganizationAccessUpdate(action="suspend"), owner=_owner_user()
    )
    auth_module._org_access_cache.clear()  # simulate the TTL having elapsed

    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "ORG_ACCESS_DISABLED" in res.json()["detail"]


def test_owner_reactivate_then_protected_request_is_allowed(monkeypatch, client, keypair):
    fake = _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="suspended")],
    )
    monkeypatch.setattr(platform_module, "service_client", lambda: fake)

    token = _token(keypair, "user-1")
    assert client.get("/whoami", headers={"Authorization": f"Bearer {token}"}).status_code == 403

    platform_module.update_organization_access(
        "org-1", OrganizationAccessUpdate(action="reactivate"), owner=_owner_user()
    )
    auth_module._org_access_cache.clear()

    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_owner_enable_then_protected_request_is_allowed_if_trial_still_valid(monkeypatch, client, keypair):
    fake = _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="active", access_enabled=False)],
    )
    monkeypatch.setattr(platform_module, "service_client", lambda: fake)

    token = _token(keypair, "user-1")
    assert client.get("/whoami", headers={"Authorization": f"Bearer {token}"}).status_code == 403

    platform_module.update_organization_access(
        "org-1", OrganizationAccessUpdate(action="enable"), owner=_owner_user()
    )
    auth_module._org_access_cache.clear()

    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200  # org enabled AND account_security still valid


# --- 13-14: deterministic organization resolution --------------------------


def test_organization_resolution_is_deterministic_single_membership(monkeypatch, client, keypair):
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1", is_default=True)],
        org_rows=[_org("org-1", status="active")],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.json()["organization_id"] == "org-1"


def test_multi_org_membership_resolves_to_default_not_first_row(monkeypatch, client, keypair):
    """The schema permits multiple memberships per user (future firm
    collaboration). Resolution must always pick the is_default=true row --
    never an arbitrary one -- regardless of insertion/list order. The
    non-default row is listed FIRST here specifically to catch a
    regression to a naive `.limit(1)` with no is_default filter."""
    _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[
            _membership_row("user-1", "org-non-default", is_default=False),
            _membership_row("user-1", "org-default", is_default=True),
        ],
        org_rows=[_org("org-non-default", status="active"), _org("org-default", status="active")],
    )
    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.json()["organization_id"] == "org-default"


# --- infra hiccup -> fail CLOSED with a controlled 503, never an implicit
# --- allow (security review round 2, 27 Aug 2026) --------------------------


def test_organization_access_lookup_failure_denies_with_503(monkeypatch, client, keypair):
    """The organizations-table lookup (access_enabled/subscription_status)
    fails -- must deny with a controlled 503, never fall through to 200.
    The previous version of this gate fell back to a stale-or-absent
    cached value here (fail open); that behavior has been removed."""
    fake = _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="active")],
    )
    real_table = fake.table

    def exploding_table(name):
        if name == "organizations":
            raise RuntimeError("simulated Supabase outage")
        return real_table(name)

    monkeypatch.setattr(fake, "table", exploding_table)

    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 503
    assert "AUTHORIZATION_UNAVAILABLE" in res.json()["detail"]
    # Never leaks the underlying infrastructure error text to the caller.
    assert "RuntimeError" not in res.text
    assert "simulated Supabase outage" not in res.text


def test_membership_lookup_failure_denies_with_503(monkeypatch, client, keypair):
    """Same fail-closed posture, one step earlier: the memberships-table
    lookup itself fails (before an organization_id is even resolved)."""
    fake = _seed(
        monkeypatch,
        account_rows=[_account_row("user-1", login_started_at=NOW)],
        membership_rows=[_membership_row("user-1", "org-1")],
        org_rows=[_org("org-1", status="active")],
    )
    real_table = fake.table

    def exploding_table(name):
        if name == "memberships":
            raise RuntimeError("simulated Supabase outage")
        return real_table(name)

    monkeypatch.setattr(fake, "table", exploding_table)

    token = _token(keypair, "user-1")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 503
    assert "AUTHORIZATION_UNAVAILABLE" in res.json()["detail"]


def test_session_start_still_bootstraps_when_user_has_no_organization_yet(monkeypatch, keypair):
    """The exempt path (/api/auth/session-start) must remain reachable for
    a genuinely brand-new user with no membership and no account_security
    row at all -- otherwise fail-closed enforcement would make it
    impossible to ever provision the first organization for anyone.
    Exercises the REAL app (real routing, real get_current_user via a
    real JWT) rather than a dependency override, so this actually proves
    _AUTH_GATE_EXEMPT_PATHS works end to end, not just in isolation."""
    from app.main import app as real_app
    from tests.test_org_provisioning import FakeRpcServiceClient

    # get_current_user()'s own checks (_check_account_not_locked /
    # _check_organization_access) both exempt this path before querying
    # anything -- this fake only needs to exist, not contain real data.
    monkeypatch.setattr(auth_module, "service_client", lambda: FakeRpcServiceClient())

    # routers/auth.py's start_session() / _ensure_organization() DO query
    # for real (account_security insert, ensure_organization_membership
    # RPC) -- this is the fake that matters for this test.
    provisioning_fake = FakeRpcServiceClient()
    monkeypatch.setattr("app.routers.auth.service_client", lambda: provisioning_fake)

    token = _token(keypair, "brand-new-user")
    client = TestClient(real_app)
    res = client.post("/api/auth/session-start", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert len(provisioning_fake.rpc_calls) == 1
