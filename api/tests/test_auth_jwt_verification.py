"""Tests for app/auth.py's local ES256/JWKS JWT verification (Auth Request
Forensics Sprint, 2026-08-13) -- replaces the remote auth.get_user() call
that production timing logs showed taking 20-64s under load. See
app/auth.py module docstring and app/db.py::jwks_client() for the design.

Exercises the real get_current_user() and _verify_jwt_locally() against a
real EC keypair and jwt.encode()'d tokens (see _es256_helpers.py) -- the
signature/expiry/issuer/audience checks are genuinely cryptographically
verified in these tests, not mocked away.

Note on mocking the JWKS fetch: jwt.PyJWKClient.fetch_data() uses
urllib.request internally, not httpx -- so respx (which only intercepts
httpx) cannot mock it. JWKS responses are mocked here by monkeypatching
PyJWKClient.fetch_data directly. respx is still used, with zero routes
registered, purely to prove no *httpx* traffic occurs (see requirement 8
tests below) -- any leftover httpx-based remote auth call would raise
under an empty respx.mock() rather than silently succeeding.
"""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest
import respx
from fastapi import Request

from app import auth as auth_module
from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.db import jwks_client

from tests._es256_helpers import (
    DEFAULT_KID,
    TEST_SUPABASE_URL,
    generate_keypair,
    jwks_body,
    make_token,
)


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-anon-key")
    get_settings.cache_clear()
    jwks_client.cache_clear()
    yield
    jwks_client.cache_clear()
    get_settings.cache_clear()


def _make_request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/api/matters", "headers": []})


def _patch_jwks(monkeypatch, body: dict) -> dict:
    """Stub PyJWKClient.fetch_data() (urllib-based -- see module docstring)
    to return `body` without any real network call. Mirrors the real
    method's side effect of populating self.jwk_set_cache so PyJWKClient's
    own Tier-1 caching behaves exactly as it would against a real
    endpoint -- otherwise every call looks like a fresh fetch. Returns a
    dict with a live "count" key so tests can assert how many times it
    actually fetched."""
    calls = {"count": 0}

    def fetch_data(self):
        calls["count"] += 1
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(body)
        return body

    monkeypatch.setattr(pyjwt.PyJWKClient, "fetch_data", fetch_data)
    return calls


def _patch_jwks_sequence(monkeypatch, bodies: list[dict]) -> dict:
    calls = {"count": 0}

    def fetch_data(self):
        idx = min(calls["count"], len(bodies) - 1)
        calls["count"] += 1
        body = bodies[idx]
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(body)
        return body

    monkeypatch.setattr(pyjwt.PyJWKClient, "fetch_data", fetch_data)
    return calls


# --- 1 & 2: valid ES256 JWT -> CurrentUser, with the correct id from `sub` ---


@respx.mock
@pytest.mark.asyncio
async def test_valid_es256_jwt_creates_current_user(monkeypatch):
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    token = make_token(priv, sub="user-42", email="nitesh@example.com")

    user = await get_current_user(_make_request(), authorization=f"Bearer {token}")

    assert isinstance(user, CurrentUser)
    assert user.id == "user-42"
    assert user.email == "nitesh@example.com"
    assert user.raw_user_meta_data == {"full_name": "Test Advocate"}


# --- 3: expired JWT -> 401 ---


@respx.mock
@pytest.mark.asyncio
async def test_expired_jwt_returns_401(monkeypatch):
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    now = int(time.time())
    token = make_token(priv, iat=now - 7200, exp=now - 3600)

    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization=f"Bearer {token}")
    assert getattr(exc_info.value, "status_code", None) == 401


# --- 4: invalid signature -> 401 ---


@respx.mock
@pytest.mark.asyncio
async def test_invalid_signature_returns_401(monkeypatch):
    priv, pub = generate_keypair()
    other_priv, _ = generate_keypair()  # different key -- signs with a key not in the JWKS
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    token = make_token(other_priv, kid=DEFAULT_KID)

    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization=f"Bearer {token}")
    assert getattr(exc_info.value, "status_code", None) == 401


@respx.mock
@pytest.mark.asyncio
async def test_wrong_audience_returns_401(monkeypatch):
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    token = make_token(priv, aud="some-other-audience")

    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization=f"Bearer {token}")
    assert getattr(exc_info.value, "status_code", None) == 401


@respx.mock
@pytest.mark.asyncio
async def test_wrong_issuer_returns_401(monkeypatch):
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    token = make_token(priv, iss="https://not-this-project.supabase.co/auth/v1")

    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization=f"Bearer {token}")
    assert getattr(exc_info.value, "status_code", None) == 401


@respx.mock
@pytest.mark.asyncio
async def test_missing_sub_returns_401(monkeypatch):
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    now = int(time.time())
    # sub is required both by our explicit `options={"require": [...]}` and
    # by get_current_user()'s own post-decode check.
    payload = {
        "email": "x@example.com",
        "aud": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + 3600,
    }
    token = pyjwt.encode(payload, priv, algorithm="ES256", headers={"kid": DEFAULT_KID})

    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization=f"Bearer {token}")
    assert getattr(exc_info.value, "status_code", None) == 401


# --- 5: invalid/missing Bearer header -> 401 (unchanged behaviour) ---


@pytest.mark.asyncio
async def test_malformed_header_returns_401():
    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization="Basic abc123")
    assert getattr(exc_info.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_empty_bearer_token_returns_401():
    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization="Bearer   ")
    assert getattr(exc_info.value, "status_code", None) == 401


# --- 6: unknown kid triggers a JWKS refresh (rotation), not a permanent failure ---


@respx.mock
@pytest.mark.asyncio
async def test_unknown_kid_triggers_jwks_refresh_not_permanent_failure(monkeypatch):
    priv1, pub1 = generate_keypair()
    priv2, pub2 = generate_keypair()

    calls = _patch_jwks_sequence(
        monkeypatch,
        [
            jwks_body((pub1, "kid-1")),  # initial fetch: only kid-1
            jwks_body((pub1, "kid-1"), (pub2, "kid-2")),  # post-rotation
        ],
    )

    token_kid1 = make_token(priv1, kid="kid-1")
    user1 = await get_current_user(_make_request(), authorization=f"Bearer {token_kid1}")
    assert user1.id == "user-abc-123"
    assert calls["count"] == 1

    # kid-2 isn't in the cached JWK set -> PyJWKClient must refetch (not
    # fail outright) before it can verify this token.
    token_kid2 = make_token(priv2, kid="kid-2")
    user2 = await get_current_user(_make_request(), authorization=f"Bearer {token_kid2}")
    assert user2.id == "user-abc-123"
    assert calls["count"] == 2

    # kid-1 is now present in the refreshed (cached) set too -- no third fetch.
    token_kid1_again = make_token(priv1, kid="kid-1")
    user3 = await get_current_user(_make_request(), authorization=f"Bearer {token_kid1_again}")
    assert user3.id == "user-abc-123"
    assert calls["count"] == 2


@respx.mock
@pytest.mark.asyncio
async def test_truly_unknown_kid_after_refresh_returns_401(monkeypatch):
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    # Signed with a kid that will never appear in the (mocked, static) JWKS.
    token = make_token(priv, kid="never-published-kid")

    with pytest.raises(Exception) as exc_info:
        await get_current_user(_make_request(), authorization=f"Bearer {token}")
    assert getattr(exc_info.value, "status_code", None) == 401


@respx.mock
@pytest.mark.asyncio
async def test_repeated_requests_reuse_cached_jwks_no_refetch(monkeypatch):
    """Requirement: JWKS retrieval cached so every request does NOT make
    another JWKS network request."""
    priv, pub = generate_keypair()
    calls = _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))

    for _ in range(5):
        token = make_token(priv)
        user = await get_current_user(_make_request(), authorization=f"Bearer {token}")
        assert user.id == "user-abc-123"

    assert calls["count"] == 1


# --- 7: user_client() receives the ORIGINAL access token ---


@respx.mock
@pytest.mark.asyncio
async def test_user_client_receives_original_token(monkeypatch):
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    token = make_token(priv)

    captured = {}

    def fake_user_client(access_token: str):
        captured["token"] = access_token
        return "fake-rls-scoped-client"

    monkeypatch.setattr(auth_module, "user_client", fake_user_client)

    user = await get_current_user(_make_request(), authorization=f"Bearer {token}")

    assert captured["token"] == token
    assert user.db == "fake-rls-scoped-client"


# --- 8: no auth.get_user() call occurs during normal authentication ---


def test_async_anon_client_no_longer_imported_by_auth_module():
    """Static proof: the old remote-verification factory isn't even
    referenced by app.auth anymore."""
    assert not hasattr(auth_module, "async_anon_client")


@respx.mock
@pytest.mark.asyncio
async def test_no_httpx_traffic_occurs_during_normal_authentication(monkeypatch):
    """Dynamic proof: zero respx routes are registered. respx.mock()
    raises on any unmocked httpx request by default -- so a passing test
    proves nothing made an httpx call (which is exactly how the old
    auth.get_user() reached Supabase). The JWKS fetch itself is urllib-
    based (see module docstring) and is separately stubbed, so it's not
    what's being proven not-to-happen here -- the httpx-based remote auth
    call is."""
    priv, pub = generate_keypair()
    _patch_jwks(monkeypatch, jwks_body((pub, DEFAULT_KID)))
    token = make_token(priv)

    user = await get_current_user(_make_request(), authorization=f"Bearer {token}")

    assert user.id == "user-abc-123"
    assert len(respx.calls) == 0
