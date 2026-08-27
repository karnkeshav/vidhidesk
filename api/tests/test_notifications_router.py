"""HTTP-level smoke tests for /api/notifications (app/routers/notifications.py)."""

from __future__ import annotations

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
        self.filters: dict = {}
        self._order = None

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, _n):
        return self

    def select(self, *_a, **_k):
        return self

    def execute(self):
        matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
        if self.op == "select":
            if self._order:
                col, desc = self._order
                matches = sorted(matches, key=lambda r: r[col], reverse=desc)
            return _FakeResponse(matches)
        if self.op == "update":
            for r in matches:
                r.update(self.payload)
            return _FakeResponse(matches)
        raise AssertionError(f"unsupported op {self.op}")


class _FakeTable:
    def __init__(self, name, rows):
        self.name = name
        self.rows = rows

    def select(self, *_a, **_k):
        return _FakeQuery(self, "select")

    def update(self, payload):
        return _FakeQuery(self, "update", payload)


class FakeDB:
    def __init__(self, notifications):
        self._tables = {"notifications": _FakeTable("notifications", notifications)}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name, []))


def _client_with(db):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u1", email="advocate@example.com", db=db, organization_id="org-1"
    )
    return TestClient(app)


def _teardown():
    app.dependency_overrides.clear()


def test_list_notifications_ordered_newest_first():
    db = FakeDB(
        [
            {"id": "n1", "type": "hearing_listed", "title": "T1", "body": "B1", "matter_id": "m1", "read_at": None, "created_at": "2026-08-01T00:00:00Z"},
            {"id": "n2", "type": "brief_ready", "title": "T2", "body": "B2", "matter_id": "m1", "read_at": None, "created_at": "2026-08-02T00:00:00Z"},
        ]
    )
    client = _client_with(db)
    try:
        resp = client.get("/api/notifications", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()]
    assert ids == ["n2", "n1"]


def test_mark_read_sets_read_at():
    db = FakeDB([{"id": "n1", "type": "hearing_listed", "title": "T1", "body": "B1", "matter_id": None, "read_at": None, "created_at": "2026-08-01T00:00:00Z"}])
    client = _client_with(db)
    try:
        resp = client.patch("/api/notifications/n1/read", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    assert resp.json()["read_at"] is not None


def test_mark_read_unknown_notification_404s():
    db = FakeDB([])
    client = _client_with(db)
    try:
        resp = client.patch("/api/notifications/nope/read", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 404
