"""Tests for PATCH /api/matters/{id} — backs the auto-generating-title
UX (Sprint 2 Phase 1 Session 1): the intake form saves an inferred title
as party names fill in, and a manual click-to-edit override.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, op, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: dict[str, object] = {}

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def limit(self, _n):
        return self

    def execute(self):
        matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
        if self.op == "select":
            return _FakeResponse(matches)
        if self.op == "update":
            for r in matches:
                r.update(self.payload)
            return _FakeResponse(matches)
        raise AssertionError(f"unsupported op {self.op}")


class _FakeTable:
    def __init__(self, name):
        self.name = name
        self.rows: list[dict] = []

    def select(self, *_a, **_k):
        return _FakeQuery(self, "select")

    def update(self, payload):
        return _FakeQuery(self, "update", payload)

    def insert(self, record):
        row = dict(record)
        row.setdefault("id", str(uuid.uuid4()))
        self.rows.append(row)
        return _FakeInsertResult(row)


class _FakeInsertResult:
    def __init__(self, row):
        self._row = row

    def execute(self):
        return _FakeResponse([self._row])


class FakeDB:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name))


def _make_client(fake_db):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="user-1", email="nitesh@example.com", db=fake_db
    )
    return TestClient(app)


def test_update_matter_title_succeeds():
    fake_db = FakeDB()
    matter = fake_db.table("matters").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "New NDA — Untitled",
         "client_name": None, "module": "contracts", "created_at": "2026-08-03T00:00:00Z"}
    ).execute().data[0]

    client = _make_client(fake_db)
    try:
        resp = client.patch(
            f"/api/matters/{matter['id']}",
            json={"title": "NDA — Ramesh Kumar / Acme"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["title"] == "NDA — Ramesh Kumar / Acme"
    assert fake_db.table("matters").rows[0]["title"] == "NDA — Ramesh Kumar / Acme"


def test_update_matter_rejects_empty_title():
    fake_db = FakeDB()
    matter = fake_db.table("matters").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "New NDA — Untitled",
         "client_name": None, "module": "contracts", "created_at": "2026-08-03T00:00:00Z"}
    ).execute().data[0]

    client = _make_client(fake_db)
    try:
        resp = client.patch(
            f"/api/matters/{matter['id']}",
            json={"title": ""},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


def test_get_matter_returns_single_matter():
    fake_db = FakeDB()
    matter = fake_db.table("matters").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "New NDA — Untitled",
         "client_name": None, "module": "contracts", "created_at": "2026-08-03T00:00:00Z"}
    ).execute().data[0]

    client = _make_client(fake_db)
    try:
        resp = client.get(
            f"/api/matters/{matter['id']}",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["id"] == matter["id"]
    assert resp.json()["title"] == "New NDA — Untitled"


def test_get_matter_404_for_unknown_matter():
    fake_db = FakeDB()
    client = _make_client(fake_db)
    try:
        resp = client.get(
            f"/api/matters/{uuid.uuid4()}",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_update_matter_404_for_unknown_matter():
    fake_db = FakeDB()
    client = _make_client(fake_db)
    try:
        resp = client.patch(
            f"/api/matters/{uuid.uuid4()}",
            json={"title": "Anything"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
