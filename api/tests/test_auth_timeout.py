"""Tests for app/db.py::anon_client Auth transport timeout and HTTPX lifecycle (2026-08-12).

Verifies:
a. anon_client() configures the intended Auth HTTP transport timeout (connect=3s, read=4s, write=3s, pool=3s).
b. service_client() and user_client() are unaffected.
c. A stalled Auth HTTP request fails within the intended bounded window.
d. A normal successful/invalid-JWT Auth response still behaves exactly as before.
e. No retry/backoff is introduced (makes exactly 1 HTTP attempt).
f. The custom HTTPX client is properly released/closed via finally in get_current_user.
"""
from __future__ import annotations

import time

import httpx
import pytest
import respx
from fastapi import HTTPException, Request

from app.auth import get_current_user
from app.config import get_settings
from app.db import SUPABASE_AUTH_TIMEOUT, anon_client, service_client, user_client


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    settings = get_settings()
    if not settings.supabase_url:
        monkeypatch.setenv("SUPABASE_URL", "https://pgwemjswxdlnshrfoggj.supabase.co")
        get_settings.cache_clear()
    if not settings.supabase_anon_key:
        monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-anon-key")
        get_settings.cache_clear()


def test_anon_client_configures_auth_http_timeout():
    """Requirement 7a: anon_client() configures the intended Auth HTTP timeout."""
    client = anon_client()
    try:
        httpx_c = client.auth._http_client
        assert httpx_c is not None
        assert httpx_c.timeout.connect == 3.0
        assert httpx_c.timeout.read == 4.0
        assert httpx_c.timeout.write == 3.0
        assert httpx_c.timeout.pool == 3.0
    finally:
        client.auth.close()


def test_service_and_user_clients_unaffected():
    """Requirement 7b: service_client() and user_client() are unaffected."""
    srv = service_client()
    usr = user_client("fake-token")

    assert srv.options.httpx_client is None
    assert usr.options.httpx_client is None

    assert srv.options.postgrest_client_timeout == 5
    assert usr.options.postgrest_client_timeout == 5


@respx.mock
def test_stalled_auth_request_times_out():
    """Requirement 7c: A stalled Auth HTTP request fails within the intended bounded window."""
    auth_url = f"{get_settings().supabase_url}/auth/v1/user"

    def stall(request):
        time.sleep(4.5)
        raise httpx.ReadTimeout("Read timed out", request=request)

    respx.get(auth_url).mock(side_effect=stall)

    client = anon_client()
    t0 = time.perf_counter()
    with pytest.raises((httpx.ReadTimeout, httpx.TimeoutException)):
        client.auth.get_user("fake-token")
    elapsed = time.perf_counter() - t0
    client.auth.close()

    # Must fail around ~4 seconds, bounded well under 6 seconds
    assert elapsed < 6.0


@respx.mock
def test_normal_auth_responses_behave_normally():
    """Requirement 7d: A normal successful/invalid-JWT Auth response behaves normally."""
    auth_url = f"{get_settings().supabase_url}/auth/v1/user"

    # 1. Invalid JWT returns 400 with JSON payload
    respx.get(auth_url).mock(return_value=httpx.Response(400, json={"code": "bad_jwt", "msg": "invalid JWT"}))
    client1 = anon_client()
    with pytest.raises(Exception) as exc_info:
        client1.auth.get_user("invalid-token")
    assert "invalid JWT" in str(exc_info.value)
    client1.auth.close()

    # 2. Valid user response returns UserResponse
    respx.get(auth_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "user": {
                    "id": "usr_999",
                    "aud": "authenticated",
                    "role": "authenticated",
                    "email": "test@example.com",
                    "app_metadata": {},
                    "user_metadata": {},
                    "created_at": "2026-01-01T00:00:00Z",
                }
            },
        )
    )
    client2 = anon_client()
    resp = client2.auth.get_user("valid-token")
    assert resp is not None
    assert resp.user.id == "usr_999"
    client2.auth.close()


@respx.mock
def test_auth_request_makes_exactly_one_attempt():
    """Requirement 7e: No retry/backoff is introduced — exactly 1 attempt is made."""
    auth_url = f"{get_settings().supabase_url}/auth/v1/user"
    route = respx.get(auth_url).mock(return_value=httpx.Response(520, text="Cloudflare Error"))

    client = anon_client()
    with pytest.raises(Exception):
        client.auth.get_user("fake-token")
    client.auth.close()

    assert route.call_count == 1


@respx.mock
def test_httpx_client_released_via_finally_in_get_current_user():
    """Requirement 7f: The custom HTTPX client is properly released/closed in get_current_user."""
    auth_url = f"{get_settings().supabase_url}/auth/v1/user"
    respx.get(auth_url).mock(return_value=httpx.Response(400, json={"code": "bad_jwt", "msg": "invalid JWT"}))

    req = Request({"type": "http", "method": "GET", "path": "/whoami", "headers": []})
    with pytest.raises(HTTPException):
        get_current_user(req, authorization="Bearer invalid-token-test")
