"""Tests for app/auth.py::get_current_user, added alongside the
Authentication Logging Enhancement (2026-08-10). Exercises the REAL
function (not app.dependency_overrides, unlike every other test in this
suite) specifically to prove two things per that sprint's Validation
requirement: (1) every HTTP status/detail is byte-identical to before
the logging was added, and (2) the new logging fires with the correct,
distinct category for each failure case.

Rewritten 2026-08-13 (Auth Request Forensics Sprint, local JWT
verification): get_current_user() no longer calls Supabase Auth's remote
auth.get_user() via async_anon_client() at all -- it verifies the JWT
locally against this project's JWKS (ES256). The old approach here
(mocking async_anon_client().auth.get_user()) no longer has anything to
attach to, since app.auth doesn't import that name anymore (see
test_auth_jwt_verification.py::test_async_anon_client_no_longer_imported_by_auth_module).
Every test below is rebuilt on real jwt.encode()'d ES256 tokens verified
against a mocked JWKS response (see _es256_helpers.py and
test_auth_jwt_verification.py's docstring on why PyJWKClient's fetch is
stubbed at the method level rather than via respx), preserving the
original intent of each test: the exact status/detail contract, and the
exact log category for each distinct failure mode.
"""
from __future__ import annotations

import logging
import time

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

from app import auth as auth_module
from app.auth import get_current_user


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-anon-key")
    get_settings.cache_clear()
    jwks_client.cache_clear()
    yield
    jwks_client.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def keypair():
    return generate_keypair()


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch, keypair):
    """All tests in this file share one JWKS response (the DEFAULT_KID
    public key) unless a test overrides fetch_data itself for a specific
    failure mode."""
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
    async def whoami(user=Depends(get_current_user)):
        return {"id": user.id}

    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


def _valid_token(keypair, **overrides) -> str:
    priv, _ = keypair
    return make_token(priv, sub="user-123", email="advocate@example.com", **overrides)


# --- Behavior-preservation: status/detail for each distinct failure mode ---


def test_missing_header_returns_422(client):
    res = client.get("/whoami")
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["header", "authorization"]


def test_no_bearer_prefix_returns_401(client):
    res = client.get("/whoami", headers={"Authorization": "Basic abc123"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Missing or malformed Authorization header"


def test_empty_bearer_token_returns_401(client):
    res = client.get("/whoami", headers={"Authorization": "Bearer    "})
    assert res.status_code == 401
    assert res.json()["detail"] == "Missing bearer token"


def test_malformed_jwt_returns_401(client):
    res = client.get("/whoami", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert res.status_code == 401
    assert res.json()["detail"].startswith("Invalid session:")


def test_expired_jwt_returns_401(client, keypair):
    now = int(time.time())
    token = _valid_token(keypair, iat=now - 7200, exp=now - 3600)
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"].startswith("Invalid session:")


def test_invalid_signature_returns_401(client, keypair):
    other_priv, _ = generate_keypair()
    token = make_token(other_priv, kid=DEFAULT_KID, sub="user-123")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"].startswith("Invalid session:")


def test_wrong_audience_returns_401(client, keypair):
    token = _valid_token(keypair, aud="not-authenticated")
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"].startswith("Invalid session:")


def test_no_sub_claim_returns_401(client, keypair):
    priv, _ = keypair
    now = int(time.time())
    payload = {
        "email": "advocate@example.com",
        "aud": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + 3600,
    }
    token = pyjwt.encode(payload, priv, algorithm="ES256", headers={"kid": DEFAULT_KID})
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_valid_token_authenticates_successfully(client, keypair):
    token = _valid_token(keypair)
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == {"id": "user-123"}


def test_lowercase_bearer_prefix_still_accepted(client, keypair):
    token = _valid_token(keypair)
    res = client.get("/whoami", headers={"Authorization": f"bearer {token}"})
    assert res.status_code == 200


# --- Logging: category correctly distinguishes each failure mode ---


def test_logs_malformed_header_category(client, caplog):
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        client.get("/whoami", headers={"Authorization": "Basic abc123"})
    assert any("category=malformed_header" in r.message for r in caplog.records)


def test_logs_invalid_jwt_category(client, caplog):
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        client.get("/whoami", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert any("category=invalid_jwt" in r.message for r in caplog.records)


def test_logs_jwt_expired_category(client, caplog, keypair):
    now = int(time.time())
    token = _valid_token(keypair, iat=now - 7200, exp=now - 3600)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert any("category=jwt_expired" in r.message for r in caplog.records)


def test_logs_invalid_signature_category(client, caplog, keypair):
    other_priv, _ = generate_keypair()
    token = make_token(other_priv, kid=DEFAULT_KID, sub="user-123")
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert any("category=invalid_jwt_signature" in r.message for r in caplog.records)


def test_logs_invalid_audience_category(client, caplog, keypair):
    token = _valid_token(keypair, aud="not-authenticated")
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert any("category=invalid_jwt_audience" in r.message for r in caplog.records)


def test_valid_login_does_not_log_a_failure(client, caplog, keypair):
    token = _valid_token(keypair)
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert not any("auth_failure" in r.message for r in caplog.records)


def test_log_line_never_contains_the_token_or_header_value(client, caplog):
    secret_token = "super-secret-jwt-value-must-never-be-logged"
    with caplog.at_level(logging.WARNING, logger="vidhidesk.auth"):
        client.get("/whoami", headers={"Authorization": f"Bearer {secret_token}"})
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
