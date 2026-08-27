"""HTTP-level tests for /api/matters/{matter_id}/court-tracking (app/
routers/court_tracking.py). Same FakeDB pattern as test_hearings.py;
service_client() (used by the manual sync-trigger endpoint) is mocked
separately to a FakeServiceClient so CourtDataGateway never makes a real
call."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.routers import court_tracking as court_tracking_router
from app.services import court_sync
from app.services.court_data_gateway import CourtDataGatewayError, CourtDataNotConfiguredError
from tests.test_platform import FakeServiceClient, _org


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, op, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: dict = {}

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def limit(self, _n):
        return self

    def select(self, *_a, **_k):
        return self

    def execute(self):
        if self.op == "select":
            matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
            return _FakeResponse(matches)
        if self.op == "insert":
            row = dict(self.payload)
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("tracking_enabled", False)
            row.setdefault("cnr_number", None)
            row.setdefault("sync_status", "idle")
            row.setdefault("last_error", None)
            row.setdefault("last_synced_at", None)
            row.setdefault("next_hearing_date", None)
            row.setdefault("provider_metadata", None)
            row.setdefault("created_at", "2026-01-01T00:00:00Z")
            row.setdefault("updated_at", "2026-01-01T00:00:00Z")
            self.table.rows.append(row)
            return _FakeResponse([row])
        if self.op == "update":
            matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
            for r in matches:
                r.update(self.payload)
            return _FakeResponse(matches)
        raise AssertionError(f"unsupported op {self.op}")


class _FakeTable:
    def __init__(self, name, seed=None):
        self.name = name
        self.rows = seed or []

    def select(self, *_a, **_k):
        return _FakeQuery(self, "select")

    def insert(self, payload):
        return _FakeQuery(self, "insert", payload)

    def update(self, payload):
        return _FakeQuery(self, "update", payload)


class FakeDB:
    def __init__(self, matters=None, tracking=None):
        self._tables = {
            "matters": _FakeTable("matters", matters or []),
            "court_case_tracking": _FakeTable("court_case_tracking", tracking or []),
        }

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name))


def _matter_row(id_="m1", organization_id="org-1"):
    return {"id": id_, "organization_id": organization_id, "user_id": "u1", "title": "Test Matter", "module": "litigation"}


def _client_with(db):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u1", email="advocate@example.com", db=db, organization_id="org-1"
    )
    return TestClient(app)


def _teardown():
    app.dependency_overrides.clear()


def test_get_tracking_creates_default_row_when_missing():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/m1/court-tracking", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["tracking_enabled"] is False
    assert body["cnr_number"] is None


def test_get_tracking_matter_not_found_404s():
    db = FakeDB(matters=[])
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/m1/court-tracking", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 404


def test_update_tracking_sets_cnr_and_enables():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.patch(
            "/api/matters/m1/court-tracking",
            json={"cnr_number": "  dlnd020047882015  ", "tracking_enabled": True},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["cnr_number"] == "DLND020047882015"  # trimmed + uppercased server-side
    assert body["tracking_enabled"] is True


def test_update_tracking_empty_body_400s():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.patch("/api/matters/m1/court-tracking", json={}, headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400


def test_update_tracking_blank_cnr_rejected():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.patch(
            "/api/matters/m1/court-tracking", json={"cnr_number": "   "}, headers={"Authorization": "Bearer x"}
        )
    finally:
        _teardown()
    assert resp.status_code == 422


def test_trigger_sync_not_configured_returns_501(monkeypatch):
    db = FakeDB(matters=[_matter_row()])
    fake_sc = FakeServiceClient(
        {
            "court_case_tracking": [
                {"id": "t1", "matter_id": "m1", "organization_id": "org-1", "cnr_number": "CNR1", "tracking_enabled": True}
            ],
            "matters": [_matter_row()],
            "organizations": [_org("org-1", status="active")],
        }
    )
    monkeypatch.setattr(court_tracking_router, "service_client", lambda: fake_sc)
    monkeypatch.setattr(
        court_sync,
        "CourtDataGateway",
        lambda: (_ for _ in ()).throw(CourtDataNotConfiguredError("no key")),
    )

    client = _client_with(db)
    try:
        resp = client.post("/api/matters/m1/court-tracking/sync", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 501


def test_trigger_sync_expired_org_returns_400(monkeypatch):
    db = FakeDB(matters=[_matter_row()])
    fake_sc = FakeServiceClient(
        {
            "court_case_tracking": [
                {"id": "t1", "matter_id": "m1", "organization_id": "org-1", "cnr_number": "CNR1", "tracking_enabled": True}
            ],
            "matters": [_matter_row()],
            "organizations": [_org("org-1", status="expired")],
        }
    )
    monkeypatch.setattr(court_tracking_router, "service_client", lambda: fake_sc)

    client = _client_with(db)
    try:
        resp = client.post("/api/matters/m1/court-tracking/sync", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400


def test_trigger_sync_provider_error_returns_502_without_leaking_detail(monkeypatch):
    db = FakeDB(matters=[_matter_row()])
    fake_sc = FakeServiceClient(
        {
            "court_case_tracking": [
                {"id": "t1", "matter_id": "m1", "organization_id": "org-1", "cnr_number": "CNR1", "tracking_enabled": True}
            ],
            "matters": [_matter_row()],
            "organizations": [_org("org-1", status="active")],
        }
    )
    monkeypatch.setattr(court_tracking_router, "service_client", lambda: fake_sc)

    class _ExplodingGateway:
        def case_lookup(self, cnr):
            raise CourtDataGatewayError("secret internal provider detail")

    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: _ExplodingGateway())

    client = _client_with(db)
    try:
        resp = client.post("/api/matters/m1/court-tracking/sync", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 502
    assert "secret internal provider detail" not in resp.text
