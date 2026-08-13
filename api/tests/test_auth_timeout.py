"""Tests for app/db.py::async_anon_client Auth transport timeout and HTTPX
lifecycle, as a standalone factory (2026-08-13).

app/auth.py::get_current_user() no longer calls async_anon_client() or
auth.get_user() at all (Auth Request Forensics Sprint, local JWT
verification, same day) -- so the get_current_user-mediated timeout/
cleanup tests that used to live in this file (wall-clock timeout on
get_user(), client.auth.close() cleanup bounded at 0.5s) no longer have
anything to exercise; that behavior is superseded by
test_auth_jwt_verification.py's tests against the new local-verification
path. What remains here tests async_anon_client(), service_client(), and
user_client() as standalone factories -- still valid, still used
elsewhere (e.g. async_anon_client() remains available as a general-
purpose factory; see its docstring in app/db.py).

Verifies:
1. async_anon_client() configures its httpx.AsyncClient auth transport timeout.
2. Healthy auth response via async_anon_client(): succeeds, cleanup occurs.
3. Immediate 400 / 520 via async_anon_client(): raises, cleanup occurs.
4. service_client() and user_client() remain synchronous/unaffected.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.config import get_settings
from app.db import (
    SUPABASE_AUTH_TIMEOUT,
    SUPABASE_POSTGREST_TIMEOUT_S,
    async_anon_client,
    service_client,
    user_client,
)


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    settings = get_settings()
    if not settings.supabase_url:
        monkeypatch.setenv("SUPABASE_URL", "https://pgwemjswxdlnshrfoggj.supabase.co")
        get_settings.cache_clear()
    if not settings.supabase_anon_key:
        monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-anon-key")
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_async_anon_client_configures_auth_http_timeout():
    """Requirement 8: async_anon_client() configures httpx.AsyncClient timeout."""
    client = await async_anon_client()
    try:
        httpx_c = client.auth._http_client
        assert isinstance(httpx_c, httpx.AsyncClient)
        assert httpx_c.timeout.connect == 3.0
        assert httpx_c.timeout.read == 4.0
        assert httpx_c.timeout.write == 3.0
        assert httpx_c.timeout.pool == 3.0
    finally:
        await client.auth.close()


def test_service_and_user_clients_unaffected():
    """Requirement 8: service_client() and user_client() remain synchronous/unaffected."""
    srv = service_client()
    usr = user_client("fake-token")

    assert srv.options.httpx_client is None
    assert usr.options.httpx_client is None

    assert srv.options.postgrest_client_timeout == SUPABASE_POSTGREST_TIMEOUT_S
    assert usr.options.postgrest_client_timeout == SUPABASE_POSTGREST_TIMEOUT_S


@respx.mock
@pytest.mark.asyncio
async def test_normal_auth_responses_behave_normally():
    """Requirement 1, 2, 3: Normal success, 400, and 520 responses behave correctly."""
    auth_url = f"{get_settings().supabase_url}/auth/v1/user"

    # 1. Invalid JWT returns 400 with JSON payload
    respx.get(auth_url).mock(return_value=httpx.Response(400, json={"code": "bad_jwt", "msg": "invalid JWT"}))
    client1 = await async_anon_client()
    with pytest.raises(Exception) as exc_info:
        await client1.auth.get_user("invalid-token")
    assert "invalid JWT" in str(exc_info.value)
    await client1.auth.close()

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
    client2 = await async_anon_client()
    resp = await client2.auth.get_user("valid-token")
    assert resp is not None
    assert resp.user.id == "usr_999"
    await client2.auth.close()

    # 3. Supabase 520 Cloudflare error raises exception
    respx.get(auth_url).mock(return_value=httpx.Response(520, text="Cloudflare Error"))
    client3 = await async_anon_client()
    with pytest.raises(Exception):
        await client3.auth.get_user("fake-token")
    await client3.auth.close()
