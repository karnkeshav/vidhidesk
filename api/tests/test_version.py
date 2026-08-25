"""Tests for GET /version (Oracle Migration Sprint) -- the deployment
identity endpoint used to prove GitHub main SHA == Oracle running SHA.
Public (no auth), matches /health's own convention.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_version_no_auth_required():
    resp = client.get("/version")
    assert resp.status_code == 200


def test_version_reports_service_name():
    resp = client.get("/version")
    assert resp.json()["service"] == "vidhidesk-api"


def test_version_falls_back_to_unknown_when_env_unset(monkeypatch):
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    resp = client.get("/version")
    assert resp.json()["commit"] == "unknown"


def test_version_reports_injected_commit_sha(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT_SHA", "abc1234")
    resp = client.get("/version")
    assert resp.json()["commit"] == "abc1234"


def test_version_never_exposes_secrets():
    """Never leaks anything beyond the four documented fields -- in
    particular, never echoes real env vars like SUPABASE_SERVICE_KEY even
    though they're set in this test process's environment."""
    resp = client.get("/version")
    body = resp.json()
    assert set(body.keys()) == {"service", "commit", "build", "environment"}
    serialized = str(body)
    for secret_env_var in ("SUPABASE_SERVICE_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        value = os.environ.get(secret_env_var)
        if value:
            assert value not in serialized
