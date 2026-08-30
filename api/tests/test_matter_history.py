"""Tests for the Matter History endpoint
(GET /api/matters/{matter_id}/hearings/{hearing_id}/history,
api/app/routers/matter_history.py). This is a thin, read-only projection
over app/services/matter_bundle.py::assemble_matter_bundle -- these tests
therefore exercise the router's auth/404 boundary and response projection,
not chronology/sorting logic itself (that is matter_bundle.py's job and is
already covered by test_matter_bundle.py).

Ownership isolation between organizations is enforced by Postgres RLS on
every table this endpoint reads (0024_tenant_foundation.sql /
0025_litigation_intelligence_ecourts.sql) -- not re-derivable in this
in-process FakeDB, so "unauthorized access" here is tested the same way
test_hearings.py/hearing_briefs.py test it: a matter_id RLS would hide
looks identical to one that doesn't exist, and _get_matter_or_404 returns
404 for both.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self.rows = rows
        self._filters: dict[str, object] = {}
        self._order = None
        self._limit = None

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        matches = [r for r in self.rows if all(r.get(k) == v for k, v in self._filters.items())]
        if self._order:
            col, desc = self._order
            matches = sorted(matches, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit is not None:
            matches = matches[: self._limit]
        return _FakeResponse(matches)


class FakeDB:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    def table(self, name):
        return _FakeTable(self.tables.setdefault(name, []))


def _make_client(fake_db):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="user-1", email="nitesh@example.com", db=fake_db, organization_id="org-test-1"
    )
    return TestClient(app)


def _seed_matter(db, matter_id="m1"):
    db.tables.setdefault("matters", []).append(
        {"id": matter_id, "organization_id": "org-test-1", "title": "Test Matter", "module": "litigation"}
    )


def _seed_hearing(db, hearing_id, matter_id="m1", hearing_at="2026-08-01T10:00:00Z", notes=None, **extra):
    row = {
        "id": hearing_id,
        "matter_id": matter_id,
        "organization_id": "org-test-1",
        "title": "A Hearing",
        "hearing_at": hearing_at,
        "notes": notes,
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
    }
    row.update(extra)
    db.tables.setdefault("hearings", []).append(row)
    return row


def _seed_party(db, matter_id="m1", **extra):
    row = {
        "id": "p1",
        "matter_id": matter_id,
        "party_type": "Petitioner",
        "party_name": "A. Advocate's Client",
        "party_number": 1,
        "created_at": "2026-08-01T00:00:00Z",
    }
    row.update(extra)
    db.tables.setdefault("litigation_parties", []).append(row)
    return row


def _seed_fact(db, matter_id="m1", **extra):
    row = {
        "id": "f1",
        "matter_id": matter_id,
        "event_date": "2026-08-01",
        "fact_summary": "Something happened.",
        "exhibit_number": None,
        "created_at": "2026-08-01T00:00:00Z",
    }
    row.update(extra)
    db.tables.setdefault("litigation_facts_evidence", []).append(row)
    return row


def _get(matter_id="m1", hearing_id="h-current"):
    return f"/api/matters/{matter_id}/hearings/{hearing_id}/history"


def test_matter_history_404_for_unknown_matter():
    """A matter_id not visible to this user's RLS-scoped db looks exactly
    like one that doesn't exist -- same equivalence hearings.py and
    hearing_briefs.py already rely on for their own _get_*_or_404 helpers."""
    fake_db = FakeDB()
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(matter_id="does-not-exist"), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_matter_history_empty_when_no_data():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["parties"] == []
    assert body["chronology"] == []
    assert body["prior_hearings"] == []
    assert body["lawyer_notes"] == []
    assert "No parties recorded for this matter." in body["missing"]
    assert "No facts/chronology recorded for this matter." in body["missing"]
    assert "No prior hearing history recorded for this matter." in body["missing"]


def test_matter_history_returns_parties_and_chronology():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_party(fake_db)
    _seed_fact(fake_db, fact_summary="Written statement filed.")
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["parties"]) == 1
    assert body["parties"][0]["party_name"] == "A. Advocate's Client"
    assert len(body["chronology"]) == 1
    assert body["chronology"][0]["fact_summary"] == "Written statement filed."
    assert "No parties recorded for this matter." not in body["missing"]


def test_matter_history_excludes_current_hearing():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_hearing(fake_db, "h-current", hearing_at="2026-08-20T10:00:00Z")
    _seed_hearing(fake_db, "h-prior", hearing_at="2026-08-01T10:00:00Z")
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(hearing_id="h-current"), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = [h["id"] for h in resp.json()["prior_hearings"]]
    assert ids == ["h-prior"]


def test_matter_history_orders_prior_hearings_most_recent_first():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_hearing(fake_db, "h-old", hearing_at="2026-07-01T10:00:00Z")
    _seed_hearing(fake_db, "h-new", hearing_at="2026-08-01T10:00:00Z")
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(hearing_id="h-current-does-not-exist"), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = [h["id"] for h in resp.json()["prior_hearings"]]
    assert ids == ["h-new", "h-old"]


def test_matter_history_orders_chronology_oldest_first():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_fact(fake_db, id="f-later", event_date="2026-08-10", fact_summary="Later fact")
    _seed_fact(fake_db, id="f-earlier", event_date="2026-08-01", fact_summary="Earlier fact")
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    summaries = [c["fact_summary"] for c in resp.json()["chronology"]]
    assert summaries == ["Earlier fact", "Later fact"]


def test_matter_history_carries_lawyer_notes_from_prior_hearings():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_hearing(fake_db, "h-prior", notes="Adjourned at respondent's request.")
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["lawyer_notes"] == ["Adjourned at respondent's request."]


def test_matter_history_handles_fact_with_missing_event_date():
    """A fact with no event_date must not crash the endpoint -- it should
    still appear, sorted after every dated entry (matter_bundle.py's
    _sort_key treats a missing date as sorting last)."""
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_fact(fake_db, id="f-dated", event_date="2026-08-01", fact_summary="Dated fact")
    _seed_fact(fake_db, id="f-undated", event_date=None, fact_summary="Undated fact")
    client = _make_client(fake_db)
    try:
        resp = client.get(_get(), headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    summaries = [c["fact_summary"] for c in resp.json()["chronology"]]
    assert summaries == ["Dated fact", "Undated fact"]
