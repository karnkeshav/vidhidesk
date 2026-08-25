"""Tests for the hearings router (/api/hearings) backing the Calendar
feature: create/list/update/delete a scheduled court appearance. Ownership
isolation between advocates is enforced by Postgres RLS on the `hearings`
table (api/migrations/0021_create_hearings.sql, same owner-only policies as
advocate_profiles/matters) — not re-derivable in this in-process FakeDB, so
these tests cover routing/validation/CRUD behavior only, mirroring
test_matters_update.py's pattern.
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
        self._order_col = None

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, col, desc=False):
        self._order_col = (col, desc)
        return self

    def limit(self, _n):
        return self

    def execute(self):
        matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
        if self._order_col:
            col, desc = self._order_col
            matches = sorted(matches, key=lambda r: r[col], reverse=desc)
        if self.op == "select":
            return _FakeResponse(matches)
        if self.op == "update":
            for r in matches:
                r.update(self.payload)
            return _FakeResponse(matches)
        if self.op == "delete":
            for r in matches:
                self.table.rows.remove(r)
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

    def delete(self):
        return _FakeQuery(self, "delete")

    def insert(self, record):
        row = dict(record)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", "2026-08-20T00:00:00Z")
        row.setdefault("updated_at", "2026-08-20T00:00:00Z")
        for optional in ("matter_id", "case_no", "court", "bench", "item_no", "stage", "notes"):
            row.setdefault(optional, None)
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


def test_create_hearing_succeeds():
    fake_db = FakeDB()
    client = _make_client(fake_db)
    try:
        resp = client.post(
            "/api/hearings",
            json={"title": "Acme Corp vs. Union of India", "hearing_at": "2026-08-26T10:30:00Z"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Acme Corp vs. Union of India"
    assert fake_db.table("hearings").rows[0]["user_id"] == "user-1"


def test_create_hearing_rejects_empty_title():
    fake_db = FakeDB()
    client = _make_client(fake_db)
    try:
        resp = client.post(
            "/api/hearings",
            json={"title": "", "hearing_at": "2026-08-26T10:30:00Z"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


def test_list_hearings_orders_by_hearing_at():
    fake_db = FakeDB()
    fake_db.table("hearings").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "Later Hearing", "hearing_at": "2026-09-01T10:00:00Z"}
    )
    fake_db.table("hearings").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "Earlier Hearing", "hearing_at": "2026-08-26T10:00:00Z"}
    )

    client = _make_client(fake_db)
    try:
        resp = client.get("/api/hearings", headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    titles = [h["title"] for h in resp.json()]
    assert titles == ["Earlier Hearing", "Later Hearing"]


def test_update_hearing_partial_fields():
    fake_db = FakeDB()
    hearing = fake_db.table("hearings").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "Draft Hearing", "hearing_at": "2026-08-26T10:00:00Z"}
    ).execute().data[0]

    client = _make_client(fake_db)
    try:
        resp = client.patch(
            f"/api/hearings/{hearing['id']}",
            json={"stage": "Final Arguments"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["stage"] == "Final Arguments"
    assert resp.json()["title"] == "Draft Hearing"


def test_update_hearing_404_for_unknown_hearing():
    fake_db = FakeDB()
    client = _make_client(fake_db)
    try:
        resp = client.patch(
            f"/api/hearings/{uuid.uuid4()}",
            json={"stage": "Final Arguments"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_delete_hearing_removes_row():
    fake_db = FakeDB()
    hearing = fake_db.table("hearings").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "Draft Hearing", "hearing_at": "2026-08-26T10:00:00Z"}
    ).execute().data[0]

    client = _make_client(fake_db)
    try:
        resp = client.delete(
            f"/api/hearings/{hearing['id']}",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert fake_db.table("hearings").rows == []


def test_delete_hearing_404_for_unknown_hearing():
    fake_db = FakeDB()
    client = _make_client(fake_db)
    try:
        resp = client.delete(
            f"/api/hearings/{uuid.uuid4()}",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
