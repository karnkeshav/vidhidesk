"""Tests for the eCourts search allowlist gate (app/services/ecourts_access.py,
wired into app/routers/court_tracking.py, 2026-09-11). Confirms: a
non-allowlisted caller is denied on every operation that can trigger a
live, billable eCourts call (search, an uncached preview, manual sync,
and enabling tracking with a CNR); a cached preview and read-only GETs
stay free for everyone; disabling tracking is never gated."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.routers import court_tracking as court_tracking_router
from app.services.court_data_gateway import CourtDataGatewayError

from tests.test_court_tracking_router import FakeDB, _matter_row


def _client_with(db, email="tester@example.com"):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u1", email=email, db=db, organization_id="org-1"
    )
    return TestClient(app)


def _teardown():
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _deny_ecourts_search(monkeypatch):
    monkeypatch.setattr(court_tracking_router, "is_ecourts_search_allowed", lambda email: False)


def test_search_denied_for_non_allowlisted_caller():
    db = FakeDB()
    client = _client_with(db)
    try:
        resp = client.get("/api/court-search?query=Sharma", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 403
    assert "ECOURTS_SEARCH_RESTRICTED" in resp.json()["detail"]


def test_uncached_preview_denied_for_non_allowlisted_caller(monkeypatch):
    db = FakeDB()
    client = _client_with(db)

    def _boom(*_a, **_k):
        raise AssertionError("live gateway must never be reached once the gate denies")

    monkeypatch.setattr(court_tracking_router.CourtDataGateway, "case_lookup", _boom)
    try:
        resp = client.get("/api/court-lookup-preview?cnr=DLND020047882015", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 403
    assert "ECOURTS_SEARCH_RESTRICTED" in resp.json()["detail"]


def test_cached_preview_stays_free_for_non_allowlisted_caller():
    tracking_row = {
        "id": "t1",
        "matter_id": "m1",
        "organization_id": "org-1",
        "cnr_number": "DLND020047882015",
        "court_name": "High Court of Delhi",
        "judge": "Hon'ble J.",
        "case_status": "Pending",
        "petitioners": ["Sharma"],
        "respondents": ["Gupta"],
        "provider_metadata": {"data": {"courtCaseData": {}}},
        "last_synced_at": "2026-09-10T00:00:00Z",
    }
    db = FakeDB(tracking=[tracking_row])
    client = _client_with(db)
    try:
        resp = client.get("/api/court-lookup-preview?cnr=DLND020047882015", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    assert resp.json()["cnr"] == "DLND020047882015"


def test_manual_sync_denied_for_non_allowlisted_caller():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.post("/api/matters/m1/court-tracking/sync", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 403
    assert "ECOURTS_SEARCH_RESTRICTED" in resp.json()["detail"]


def test_enabling_tracking_with_a_cnr_is_denied_for_non_allowlisted_caller():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.patch(
            "/api/matters/m1/court-tracking",
            json={"cnr_number": "DLND020047882015", "tracking_enabled": True},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()
    assert resp.status_code == 403
    assert "ECOURTS_SEARCH_RESTRICTED" in resp.json()["detail"]


def test_disabling_tracking_is_never_gated():
    db = FakeDB(
        matters=[_matter_row()],
        tracking=[
            {
                "id": "t1",
                "matter_id": "m1",
                "organization_id": "org-1",
                "tracking_enabled": True,
                "cnr_number": "DLND020047882015",
                "sync_status": "synced",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
    )
    client = _client_with(db)
    try:
        resp = client.patch(
            "/api/matters/m1/court-tracking",
            json={"tracking_enabled": False},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()
    assert resp.status_code == 200
    assert resp.json()["tracking_enabled"] is False


def test_get_tracking_read_is_never_gated():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/m1/court-tracking", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
