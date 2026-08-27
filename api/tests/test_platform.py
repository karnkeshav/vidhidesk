"""Tests for the platform-owner API (/api/platform/*, app/routers/platform.py)
and app/auth.py::require_platform_owner. Ownership-isolation between
organizations is enforced by Postgres RLS at the DB layer (not re-derivable
in this in-process FakeDB, same limitation test_hearings.py documents) --
these tests cover authorization (owner-only access), data aggregation, and
the access-update state machine.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError

from app.auth import CurrentUser, get_current_user, require_platform_owner
from app.main import app


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, op, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: dict[str, object] = {}
        self._in_filters: dict[str, list] = {}
        self._order_col = None

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def in_(self, col, vals):
        self._in_filters[col] = list(vals)
        return self

    def order(self, col, desc=False):
        self._order_col = (col, desc)
        return self

    def limit(self, _n):
        return self

    def select(self, *_args, **_kwargs):
        return self

    def _matches(self, row):
        if not all(row.get(k) == v for k, v in self.filters.items()):
            return False
        if not all(row.get(k) in v for k, v in self._in_filters.items()):
            return False
        return True

    def execute(self):
        if self.op == "select":
            matches = [r for r in self.table.rows if self._matches(r)]
            if self._order_col:
                col, desc = self._order_col
                matches = sorted(matches, key=lambda r: r[col], reverse=desc)
            return _FakeResponse(matches)
        if self.op == "insert":
            row = dict(self.payload)
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            row.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
            self.table.rows.append(row)
            return _FakeResponse([row])
        if self.op == "update":
            matches = [r for r in self.table.rows if self._matches(r)]
            for r in matches:
                r.update(self.payload)
            return _FakeResponse(matches)
        raise AssertionError(f"unsupported op {self.op}")


class _FakeTable:
    def __init__(self, name, seed=None):
        self.name = name
        self.rows = seed or []

    def select(self, *_args, **_kwargs):
        return _FakeQuery(self, "select")

    def insert(self, payload):
        return _FakeQuery(self, "insert", payload)

    def update(self, payload):
        return _FakeQuery(self, "update", payload)


class _FakeAdminUsers:
    def get_user_by_id(self, _user_id):
        # Matches the REAL exception type app/routers/platform.py's
        # get_organization() catches (supabase_auth.errors.AuthApiError,
        # verified against the installed SDK during the 27 Aug 2026
        # security review -- see that function's own comment). A generic
        # RuntimeError here would no longer be caught by the narrowed
        # `except AuthApiError`, which is exactly the kind of drift this
        # fixture needs to track, not paper over.
        raise AuthApiError("admin API unavailable in tests", 500, None)


class _FakeAuth:
    admin = _FakeAdminUsers()


class FakeServiceClient:
    def __init__(self, seed_tables: dict[str, list[dict]]):
        self._tables = {name: _FakeTable(name, rows) for name, rows in seed_tables.items()}
        self.auth = _FakeAuth()

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name))


def _org(id_, org_type="individual", status="active", **overrides):
    now = datetime.now(timezone.utc)
    row = {
        "id": id_,
        "name": f"Org {id_}",
        "organization_type": org_type,
        "subscription_status": status,
        "trial_started_at": now.isoformat(),
        "trial_ends_at": (now + timedelta(days=5)).isoformat(),
        "access_enabled": status in ("trial", "active"),
        "payment_marked_at": None,
        "payment_marked_by": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    row.update(overrides)
    return row


@pytest.fixture
def owner_user():
    return CurrentUser(id="owner-1", email="keshav.karn@gmail.com", db=None, organization_id=None)


@pytest.fixture
def other_user():
    return CurrentUser(id="user-2", email="someone-else@example.com", db=None, organization_id="org-a")


def _client_as(user):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _teardown():
    app.dependency_overrides.clear()


def test_non_owner_gets_403(other_user):
    client = _client_as(other_user)
    try:
        resp = client.get("/api/platform/overview", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 403


def test_owner_email_is_case_insensitive_and_trimmed(monkeypatch):
    user = CurrentUser(id="owner-1", email="  Keshav.Karn@Gmail.com  ", db=None)
    fake = FakeServiceClient({"organizations": [], "matters": [], "draft_versions": [], "account_security": [], "memberships": []})
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(user)
    try:
        resp = client.get("/api/platform/overview", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200


def test_overview_aggregates_counts(monkeypatch, owner_user):
    fake = FakeServiceClient(
        {
            "organizations": [
                _org("o1", org_type="individual", status="trial"),
                _org("o2", org_type="firm", status="active"),
                _org("o3", org_type="individual", status="suspended"),
                _org("o4", org_type="individual", status="expired"),
            ],
            "matters": [
                {"user_id": "u1", "id": "m1"},
                {"user_id": "u1", "id": "m2"},
                {"user_id": "u2", "id": "m3"},
            ],
            "draft_versions": [{"matter_id": "m1"}],
            "account_security": [{"user_id": "u1"}, {"user_id": "u2"}, {"user_id": "u3"}],
            "memberships": [{"user_id": "u1"}, {"user_id": "u2"}],
        }
    )
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)

    client = _client_as(owner_user)
    try:
        resp = client.get("/api/platform/overview", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_organizations"] == 4
    assert body["individual_organizations"] == 3
    assert body["firm_organizations"] == 1
    assert body["trial_organizations"] == 1
    assert body["active_organizations"] == 1
    assert body["suspended_organizations"] == 1
    assert body["expired_organizations"] == 1
    assert body["users_with_a_matter"] == 2  # u1, u2
    assert body["users_with_a_draft"] == 1  # u1 (owns m1)
    assert body["onboarding_funnel"]["registered"] == 3
    assert body["onboarding_funnel"]["organization_created"] == 2
    assert body["onboarding_funnel"]["first_matter_created"] == 2
    assert body["onboarding_funnel"]["first_draft_generated"] == 1


def test_list_organizations_rejects_invalid_status_filter(monkeypatch, owner_user):
    fake = FakeServiceClient({"organizations": [], "memberships": [], "matters": []})
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.get("/api/platform/organizations?status=bogus", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400


def test_list_organizations_returns_member_and_matter_counts(monkeypatch, owner_user):
    fake = FakeServiceClient(
        {
            "organizations": [_org("o1"), _org("o2", status="trial")],
            "memberships": [
                {"organization_id": "o1", "user_id": "u1"},
                {"organization_id": "o1", "user_id": "u2"},
                {"organization_id": "o2", "user_id": "u3"},
            ],
            "matters": [
                {"organization_id": "o1", "id": "m1"},
                {"organization_id": "o1", "id": "m2"},
            ],
        }
    )
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.get("/api/platform/organizations", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    by_id = {row["id"]: row for row in resp.json()}
    assert by_id["o1"]["member_count"] == 2
    assert by_id["o1"]["matter_count"] == 2
    assert by_id["o2"]["member_count"] == 1
    assert by_id["o2"]["matter_count"] == 0


def test_access_update_mark_payment_sets_active_and_logs_event(monkeypatch, owner_user):
    fake = FakeServiceClient({"organizations": [_org("o1", status="trial")], "organization_access_events": []})
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.patch(
            "/api/platform/organizations/o1/access",
            json={"action": "mark_payment", "reason": "Paid via bank transfer"},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()

    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription_status"] == "active"
    assert body["access_enabled"] is True
    assert body["payment_marked_at"] is not None

    events = fake.table("organization_access_events").rows
    assert len(events) == 1
    assert events[0]["action"] == "mark_payment"
    assert events[0]["previous_status"] == "trial"
    assert events[0]["new_status"] == "active"
    assert events[0]["actor_user_id"] == "owner-1"
    assert events[0]["reason"] == "Paid via bank transfer"


def test_access_update_suspend_disables_access(monkeypatch, owner_user):
    fake = FakeServiceClient({"organizations": [_org("o1", status="active")], "organization_access_events": []})
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.patch(
            "/api/platform/organizations/o1/access",
            json={"action": "suspend"},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription_status"] == "suspended"
    assert body["access_enabled"] is False


def test_access_update_unknown_org_404s(monkeypatch, owner_user):
    fake = FakeServiceClient({"organizations": []})
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.patch(
            "/api/platform/organizations/nope/access",
            json={"action": "suspend"},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()
    assert resp.status_code == 404


def test_access_update_rejects_invalid_action(monkeypatch, owner_user):
    fake = FakeServiceClient({"organizations": [_org("o1")]})
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.patch(
            "/api/platform/organizations/o1/access",
            json={"action": "delete_everything"},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()
    assert resp.status_code == 422  # Pydantic Field(pattern=...) rejects it


def test_organization_detail_includes_members_and_modules(monkeypatch, owner_user):
    fake = FakeServiceClient(
        {
            "organizations": [_org("o1")],
            "memberships": [{"id": "mm1", "organization_id": "o1", "user_id": "u1", "role": "org_admin", "created_at": "2026-01-01T00:00:00Z"}],
            "matters": [
                {"module": "contracts", "organization_id": "o1", "created_at": "2026-01-02T00:00:00Z"},
                {"module": "rera", "organization_id": "o1", "created_at": "2026-01-03T00:00:00Z"},
            ],
        }
    )
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.get("/api/platform/organizations/o1", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["matter_count"] == 2
    assert sorted(body["modules_used"]) == ["contracts", "rera"]
    assert len(body["members"]) == 1
    assert body["members"][0]["role"] == "org_admin"
    # Admin email enrichment is best-effort -- the fake admin API always
    # raises, so this must degrade to None rather than 500.
    assert body["members"][0]["email"] is None


# --- Dashboard clarity: per-member account_status (security review round
# --- 3, 27 Aug 2026) ---------------------------------------------------


class TestAccountStatus:
    """Unit tests for _account_status -- must mirror
    app/auth.py::_check_account_not_locked's exact precedence
    (payment_received first, then no-row-yet, then the TRIAL_WINDOW
    comparison) so the dashboard can never show a status inconsistent
    with what actually gates that member's requests."""

    def test_no_row_is_not_started(self):
        from app.routers.platform import _account_status

        assert _account_status(None) == "not_started"

    def test_payment_received_wins_even_if_trial_also_expired(self):
        from app.routers.platform import _account_status

        row = {
            "payment_received": True,
            "login_started_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        }
        assert _account_status(row) == "payment_received"

    def test_recent_login_is_trial_active(self):
        from app.routers.platform import _account_status

        row = {"payment_received": False, "login_started_at": datetime.now(timezone.utc).isoformat()}
        assert _account_status(row) == "trial_active"

    def test_login_past_five_days_is_trial_expired(self):
        from app.routers.platform import _account_status

        row = {
            "payment_received": False,
            "login_started_at": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
        }
        assert _account_status(row) == "trial_expired"

    def test_row_with_no_login_started_at_is_not_started(self):
        from app.routers.platform import _account_status

        row = {"payment_received": False, "login_started_at": None}
        assert _account_status(row) == "not_started"


def test_organization_detail_includes_account_status_per_member(monkeypatch, owner_user):
    now = datetime.now(timezone.utc)
    fake = FakeServiceClient(
        {
            "organizations": [_org("o1")],
            "memberships": [
                {"id": "mm1", "organization_id": "o1", "user_id": "u1", "role": "org_admin", "created_at": "2026-01-01T00:00:00Z"},
                {"id": "mm2", "organization_id": "o1", "user_id": "u2", "role": "member", "created_at": "2026-01-01T00:00:00Z"},
                {"id": "mm3", "organization_id": "o1", "user_id": "u3", "role": "member", "created_at": "2026-01-01T00:00:00Z"},
            ],
            "account_security": [
                {"user_id": "u1", "login_started_at": now.isoformat(), "payment_received": False},
                {"user_id": "u2", "login_started_at": (now - timedelta(days=6)).isoformat(), "payment_received": False},
                # u3 has no account_security row at all (never called session-start)
            ],
            "matters": [],
        }
    )
    monkeypatch.setattr("app.routers.platform.service_client", lambda: fake)
    client = _client_as(owner_user)
    try:
        resp = client.get("/api/platform/organizations/o1", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()

    assert resp.status_code == 200
    by_user = {m["user_id"]: m["account_status"] for m in resp.json()["members"]}
    assert by_user["u1"] == "trial_active"
    assert by_user["u2"] == "trial_expired"
    assert by_user["u3"] == "not_started"
    # Sensitive raw fields never leak through -- only the coarse category.
    assert "login_started_at" not in resp.text
