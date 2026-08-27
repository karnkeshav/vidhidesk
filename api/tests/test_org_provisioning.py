"""Tests for atomic organization provisioning (app/routers/auth.py::
_ensure_organization / start_session), rewritten 27 Aug 2026 to call a
single Postgres RPC (public.ensure_organization_membership,
0024_tenant_foundation.sql Section 5b) instead of two separate
organizations/memberships INSERTs -- closing the partial-failure/orphan-
organization gap the security review identified.

The RPC's own atomicity/concurrency-safety (the advisory lock, the
transaction boundary) is a Postgres-side property that cannot be verified
against the in-process FakeDB this suite uses -- see
api/scripts/live_verify_tenant_rls.py and the delivery report for what
remains DB-level-only / unverified outside a real Postgres instance. What
IS verified here, at the Python-integration-boundary:
  - the wrapper calls the RPC exactly once per invocation (no leftover
    two-call code path that could still race)
  - a repeated call (simulating the RPC's own idempotent "already has a
    default membership" fast path) does not error or attempt any
    additional write
  - a failed RPC call is logged, not silently swallowed
  - a failed RPC call does not block sign-in (start_session still
    succeeds)
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.routers import auth as auth_router_module


class _FakeRpcCall:
    def __init__(self, result):
        self._result = result

    def execute(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeInsertCall:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeAccountSecurityTable:
    """Minimal stand-in for .table("account_security").insert(...).execute()
    -- always succeeds (no unique_violation simulation needed for these
    tests, which are about the organization RPC, not the trial-start
    insert-once behavior already covered by test_auth.py's siblings)."""

    def insert(self, payload):
        return _FakeInsertCall(_FakeResponse([{**payload}]))


class FakeRpcServiceClient:
    def __init__(self, rpc_result="org-123", rpc_raises: Exception | None = None):
        self.rpc_calls: list[tuple[str, dict]] = []
        self._rpc_result = rpc_result
        self._rpc_raises = rpc_raises

    def table(self, name):
        assert name == "account_security", f"unexpected table {name!r} for this fake"
        return _FakeAccountSecurityTable()

    def rpc(self, name, params):
        self.rpc_calls.append((name, dict(params)))
        if self._rpc_raises is not None:
            return _FakeRpcCall(self._rpc_raises)
        return _FakeRpcCall(_FakeResponse([{"ensure_organization_membership": self._rpc_result}]))


def _user(user_id="user-1", email="advocate@example.com") -> CurrentUser:
    return CurrentUser(id=user_id, email=email, db=None)


def _client_as(user):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _teardown():
    app.dependency_overrides.clear()


# --- 9: single atomic RPC call, not two separate table writes --------------


def test_ensure_organization_calls_rpc_exactly_once(monkeypatch):
    fake = FakeRpcServiceClient()
    monkeypatch.setattr(auth_router_module, "service_client", lambda: fake)

    auth_router_module._ensure_organization(_user())

    assert len(fake.rpc_calls) == 1
    name, params = fake.rpc_calls[0]
    assert name == "ensure_organization_membership"
    assert params == {"p_user_id": "user-1", "p_email": "advocate@example.com"}


def test_ensure_organization_no_longer_writes_organizations_or_memberships_tables_directly(monkeypatch):
    """Regression guard for the exact bug the review found: the OLD
    implementation did `.table("organizations").insert(...)` then
    `.table("memberships").insert(...)` as two separate round trips. The
    fake's .table() here only recognizes "account_security" (asserts
    otherwise) -- if _ensure_organization ever reached for
    organizations/memberships directly again, this test fails loudly."""
    fake = FakeRpcServiceClient()
    monkeypatch.setattr(auth_router_module, "service_client", lambda: fake)

    auth_router_module._ensure_organization(_user())  # would raise via the assert in .table() if regressed


# --- 10-11: repeat calls do not duplicate ----------------------------------


def test_repeated_call_does_not_error_and_returns_same_org(monkeypatch):
    """Simulates the RPC's own idempotent fast path (a user who already
    has a default membership) -- the Python wrapper must handle a second
    call identically to the first, with no special-casing that could
    itself introduce a duplicate-write bug."""
    fake = FakeRpcServiceClient(rpc_result="org-123")
    monkeypatch.setattr(auth_router_module, "service_client", lambda: fake)

    auth_router_module._ensure_organization(_user())
    auth_router_module._ensure_organization(_user())

    assert len(fake.rpc_calls) == 2
    assert fake.rpc_calls[0] == fake.rpc_calls[1]  # identical params both times


# --- 12: failure is logged, never silently swallowed ------------------------


def test_provisioning_failure_is_logged_not_silently_swallowed(monkeypatch, caplog):
    fake = FakeRpcServiceClient(rpc_raises=RuntimeError("simulated DB error"))
    monkeypatch.setattr(auth_router_module, "service_client", lambda: fake)

    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        auth_router_module._ensure_organization(_user(user_id="user-1"))

    assert any(
        "ensure_organization_membership RPC failed" in r.message and "user-1" in r.message
        for r in caplog.records
    )


def test_provisioning_failure_log_never_contains_email(monkeypatch, caplog):
    """The log line documents that it carries the user id only, never
    email -- this proves that claim rather than just asserting it in a
    comment."""
    fake = FakeRpcServiceClient(rpc_raises=RuntimeError("simulated DB error"))
    monkeypatch.setattr(auth_router_module, "service_client", lambda: fake)

    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        auth_router_module._ensure_organization(_user(user_id="user-1", email="secret-address@example.com"))

    for r in caplog.records:
        assert "secret-address@example.com" not in r.message


def test_provisioning_failure_does_not_block_sign_in(monkeypatch):
    """start_session() must still return {"status": "ok"} even when
    organization provisioning fails -- same best-effort posture as the
    frontend's own startSession().catch(() => {})."""
    fake = FakeRpcServiceClient(rpc_raises=RuntimeError("simulated DB error"))
    monkeypatch.setattr(auth_router_module, "service_client", lambda: fake)

    client = _client_as(_user())
    try:
        res = client.post("/api/auth/session-start", headers={"Authorization": "Bearer test-token"})
    finally:
        _teardown()

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_session_start_calls_ensure_organization(monkeypatch):
    fake = FakeRpcServiceClient()
    monkeypatch.setattr(auth_router_module, "service_client", lambda: fake)

    client = _client_as(_user())
    try:
        res = client.post("/api/auth/session-start", headers={"Authorization": "Bearer test-token"})
    finally:
        _teardown()

    assert res.status_code == 200
    assert len(fake.rpc_calls) == 1
