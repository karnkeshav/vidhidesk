"""Tests for app/auth.py::get_current_user, added alongside the
Authentication Logging Enhancement (2026-08-10). Exercises the REAL
function (not app.dependency_overrides, unlike every other test in this
suite) specifically to prove two things per that sprint's Validation
requirement: (1) every HTTP status/detail is byte-identical to before
the logging was added, and (2) the new logging fires with the correct,
distinct category for each of the six failure cases the Authentication
Investigation Sprint identified.
"""
from __future__ import annotations

import logging

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import auth as auth_module
from app.auth import get_current_user


class _FakeUser:
    def __init__(self, id_: str, email: str):
        self.id = id_
        self.email = email
        self.user_metadata = {}


class _FakeGetUserResponse:
    def __init__(self, user):
        self.user = user


class _FakeAnonClient:
    """Stands in for app.db.anon_client() — controls exactly what
    .auth.get_user(token) returns/raises, without any real network call."""

    def __init__(self, behavior):
        self._behavior = behavior  # callable(token) -> response, or raises

    @property
    def auth(self):
        return self

    def get_user(self, token: str):
        return self._behavior(token)


def _make_app(anon_client_factory):
    app = FastAPI()

    @app.get("/whoami")
    def whoami(user=Depends(get_current_user)):
        return {"id": user.id}

    return app


@pytest.fixture
def client(monkeypatch):
    def _client_for(behavior):
        monkeypatch.setattr(auth_module, "anon_client", lambda: _FakeAnonClient(behavior))
        app = _make_app(None)
        return TestClient(app)

    return _client_for


def _valid_behavior(token: str):
    return _FakeGetUserResponse(_FakeUser("user-123", "advocate@example.com"))


# --- Behavior-preservation: every status/detail must match pre-logging exactly ---

def test_missing_header_returns_422_unchanged(client):
    c = client(_valid_behavior)
    res = c.get("/whoami")
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["header", "authorization"]


def test_no_bearer_prefix_returns_401_unchanged(client):
    c = client(_valid_behavior)
    res = c.get("/whoami", headers={"Authorization": "Basic abc123"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Missing or malformed Authorization header"


def test_empty_bearer_token_returns_401_unchanged(client):
    c = client(_valid_behavior)
    res = c.get("/whoami", headers={"Authorization": "Bearer    "})
    assert res.status_code == 401
    assert res.json()["detail"] == "Missing bearer token"


def test_malformed_jwt_returns_401_unchanged(client):
    def behavior(token):
        raise Exception("invalid JWT: unable to parse or verify signature, token is malformed: token contains an invalid number of segments")

    c = client(behavior)
    res = c.get("/whoami", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert res.status_code == 401
    assert res.json()["detail"].startswith("Invalid session:")


def test_revoked_session_returns_401_unchanged(client):
    def behavior(token):
        raise Exception("Session from session_id claim in JWT does not exist")

    c = client(behavior)
    res = c.get("/whoami", headers={"Authorization": "Bearer some-otherwise-valid-looking-token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid session: Session from session_id claim in JWT does not exist"


def test_generic_supabase_failure_returns_401_unchanged(client):
    def behavior(token):
        raise Exception("connection reset by peer")

    c = client(behavior)
    res = c.get("/whoami", headers={"Authorization": "Bearer some-token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid session: connection reset by peer"


def test_no_user_returned_returns_401_unchanged(client):
    def behavior(token):
        return _FakeGetUserResponse(None)

    c = client(behavior)
    res = c.get("/whoami", headers={"Authorization": "Bearer some-token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid or expired session"


def test_valid_token_authenticates_successfully_unchanged(client):
    c = client(_valid_behavior)
    res = c.get("/whoami", headers={"Authorization": "Bearer a-real-token"})
    assert res.status_code == 200
    assert res.json() == {"id": "user-123"}


def test_lowercase_bearer_prefix_still_accepted_unchanged(client):
    c = client(_valid_behavior)
    res = c.get("/whoami", headers={"Authorization": "bearer a-real-token"})
    assert res.status_code == 200


# --- New logging: category correctly distinguishes each failure mode ---

def test_logs_malformed_header_category(client, caplog):
    c = client(_valid_behavior)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        c.get("/whoami", headers={"Authorization": "Basic abc123"})
    assert any("category=malformed_header" in r.message for r in caplog.records)


def test_logs_invalid_jwt_category(client, caplog):
    def behavior(token):
        raise Exception("invalid JWT: unable to parse or verify signature, token is malformed: token contains an invalid number of segments")

    c = client(behavior)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        c.get("/whoami", headers={"Authorization": "Bearer bad"})
    assert any("category=invalid_jwt" in r.message for r in caplog.records)


def test_logs_session_expired_or_revoked_category(client, caplog):
    def behavior(token):
        raise Exception("Session from session_id claim in JWT does not exist")

    c = client(behavior)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        c.get("/whoami", headers={"Authorization": "Bearer stale"})
    assert any("category=session_expired_or_revoked" in r.message for r in caplog.records)


def test_logs_supabase_verification_failed_category(client, caplog):
    def behavior(token):
        raise Exception("connection reset by peer")

    c = client(behavior)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        c.get("/whoami", headers={"Authorization": "Bearer token"})
    assert any("category=supabase_verification_failed" in r.message for r in caplog.records)


def test_logs_no_user_returned_category(client, caplog):
    def behavior(token):
        return _FakeGetUserResponse(None)

    c = client(behavior)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        c.get("/whoami", headers={"Authorization": "Bearer token"})
    assert any("category=no_user_returned" in r.message for r in caplog.records)


def test_valid_login_does_not_log_a_failure(client, caplog):
    c = client(_valid_behavior)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        c.get("/whoami", headers={"Authorization": "Bearer good-token"})
    assert not any("auth_failure" in r.message for r in caplog.records)


def test_log_line_never_contains_the_token_or_header_value(client, caplog):
    secret_token = "super-secret-jwt-value-must-never-be-logged"

    def behavior(token):
        raise Exception("invalid JWT: unable to parse or verify signature, token is malformed: token contains an invalid number of segments")

    c = client(behavior)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        c.get("/whoami", headers={"Authorization": f"Bearer {secret_token}"})
    for r in caplog.records:
        assert secret_token not in r.message


def test_missing_header_logged_via_main_exception_handler(monkeypatch, caplog):
    """The 422 path bypasses get_current_user entirely (FastAPI's own
    Header(...) validation rejects it first) -- covered by main.py's
    exception handler instead. Exercised against the real app to prove
    the handler is actually wired, not just unit-tested in isolation."""
    from app.main import app as real_app

    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        with TestClient(real_app) as c:
            res = c.get("/api/matters")
    assert res.status_code == 422
    assert any("category=missing_header" in r.message and "status=422" in r.message for r in caplog.records)
