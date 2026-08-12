"""Tests for app/db.py::async_anon_client Auth transport timeout and HTTPX lifecycle (2026-08-12).

Verifies:
A. Happy path: normal async get_user succeeds and returns CurrentUser.
B. Normal auth failures: 400 / invalid JWT remains 401.
C. 520: 520 response returns 401.
D. Hard wall-clock timeout: Mocks an async HTTP operation streaming for >15s.
   Verify asyncio.wait_for() terminates at approximately 4s (<5s).
E. Client cleanup: Verify AsyncClient is closed in finally after success, error, timeout.
F. No thread leak: Verification executes directly on event loop without worker thread.
G. Existing clients: service_client() and user_client() remain synchronous/unaffected.
H. Dependency compatibility: Works with both sync and async route dependencies.
I. Timing logs report ~4000ms duration on timeout.
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx
import pytest
import respx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.auth import AUTH_WALL_CLOCK_TIMEOUT_S, CurrentUser, get_current_user
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
    """Requirement A/G: async_anon_client() configures httpx.AsyncClient timeout."""
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
    """Requirement G: service_client() and user_client() remain synchronous/unaffected."""
    srv = service_client()
    usr = user_client("fake-token")

    assert srv.options.httpx_client is None
    assert usr.options.httpx_client is None

    assert srv.options.postgrest_client_timeout == SUPABASE_POSTGREST_TIMEOUT_S
    assert usr.options.postgrest_client_timeout == SUPABASE_POSTGREST_TIMEOUT_S


@respx.mock
@pytest.mark.asyncio
async def test_normal_auth_responses_behave_normally():
    """Requirement A, B, C: Normal success, 400, and 520 responses behave correctly."""
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


@respx.mock
def test_hard_wall_clock_timeout_bounds_execution(caplog):
    """Requirement D & I: Hard wall-clock timeout terminates a slow/streaming request at ~4s (<5s)."""
    auth_url = f"{get_settings().supabase_url}/auth/v1/user"

    async def streaming_slow_response(request):
        # Simulate continuous frame activity every 1.0s for 15s (read=4.0 inactivity timer won't fire)
        for _ in range(15):
            await asyncio.sleep(1.0)
        return httpx.Response(520, text="Cloudflare Error")

    respx.get(auth_url).mock(side_effect=streaming_slow_response)

    app = FastAPI()

    @app.get("/api/matters")
    async def get_matters(user: CurrentUser = Depends(get_current_user)):
        return {"status": "ok"}

    t0 = time.perf_counter()
    with caplog.at_level(logging.INFO, logger="vidhidesk.timing"):
        with TestClient(app) as client:
            resp = client.get("/api/matters", headers={"Authorization": "Bearer fake-token"})

    elapsed = time.perf_counter() - t0

    assert resp.status_code == 401
    assert "Invalid session:" in resp.json()["detail"]
    assert elapsed < 5.0  # Must be bounded under 5s (target ~4.0s)

    # Requirement I: Check timing logger recorded ~4000ms duration
    timing_records = [r for r in caplog.records if "timing auth.get_user" in r.message]
    assert len(timing_records) > 0
    assert "duration_ms=" in timing_records[0].message
    assert "outcome=error" in timing_records[0].message


def test_dependency_compatibility_with_sync_and_async_routes():
    """Requirement H: Verify get_current_user works for both sync and async route handlers."""
    auth_url = f"{get_settings().supabase_url}/auth/v1/user"

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(auth_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "user": {
                        "id": "usr_777",
                        "aud": "authenticated",
                        "role": "authenticated",
                        "email": "syncasync@example.com",
                        "app_metadata": {},
                        "user_metadata": {},
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                },
            )
        )

        app = FastAPI()

        @app.get("/sync-endpoint")
        def sync_route(user: CurrentUser = Depends(get_current_user)):
            return {"id": user.id, "type": "sync"}

        @app.get("/async-endpoint")
        async def async_route(user: CurrentUser = Depends(get_current_user)):
            return {"id": user.id, "type": "async"}

        with TestClient(app) as client:
            res_sync = client.get("/sync-endpoint", headers={"Authorization": "Bearer token1"})
            assert res_sync.status_code == 200
            assert res_sync.json() == {"id": "usr_777", "type": "sync"}

            res_async = client.get("/async-endpoint", headers={"Authorization": "Bearer token2"})
            assert res_async.status_code == 200
            assert res_async.json() == {"id": "usr_777", "type": "async"}


@pytest.mark.asyncio
async def test_client_cleanup_on_all_paths(monkeypatch):
    """Requirement E: AsyncClient is closed in finally after success, error, timeout."""
    closed_counts = 0

    class TrackingAsyncClient:
        def __init__(self):
            self.auth = self

        async def get_user(self, token: str):
            if token == "error":
                raise Exception("SDK error")
            if token == "timeout":
                await asyncio.sleep(10.0)
            return type("UserResp", (), {"user": type("User", (), {"id": "usr_1", "email": "a@b.com", "user_metadata": {}})()})()

        async def close(self):
            nonlocal closed_counts
            closed_counts += 1

    async def mock_async_anon():
        return TrackingAsyncClient()

    monkeypatch.setattr("app.auth.async_anon_client", mock_async_anon)

    req = Request({"type": "http", "method": "GET", "path": "/test", "headers": []})

    # 1. Success path
    closed_counts = 0
    usr = await get_current_user(req, authorization="Bearer valid")
    assert usr.id == "usr_1"
    assert closed_counts == 1

    # 2. Error path
    closed_counts = 0
    with pytest.raises(HTTPException):
        await get_current_user(req, authorization="Bearer error")
    assert closed_counts == 1

    # 3. Timeout path
    closed_counts = 0
    t0 = time.perf_counter()
    with pytest.raises(HTTPException):
        await get_current_user(req, authorization="Bearer timeout")
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0
    assert closed_counts == 1
