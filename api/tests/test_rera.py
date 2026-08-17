"""Tests for the RERA & Real Estate Phase 1 backend:
app/services/rera.py (state/procedure/step retrieval + walkthrough
progress) and app/routers/rera.py (auth/HTTP wiring).

Property deeds and RERA complaints are NOT tested here — they reuse the
existing generate_draft()/templates pipeline, already covered by
test_contracts.py/test_clause_generator.py-style tests; there is no new
drafting code path for this module to test in isolation. See
docs/30_Implementation/RERA_BACKEND_INTEGRATION_CONTRACT.md.

All tests run against an in-memory FakeDB — per this project's own "never
allow unit tests to write to production" rule (docs/30_Implementation/
Backlog.md's documented risk), no test here touches real Supabase.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import rera


# --- Fake DB (same shape/convention as test_matters_update.py's FakeDB,
# extended with order()/limit()/is_() since rera.py's queries use them) ----


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, op, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: dict[str, object] = {}
        self.null_filters: list[str] = []
        self._order_col = None
        self._limit = None

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def is_(self, col, val):
        assert val == "null", "only null-check supported by this fake"
        self.null_filters.append(col)
        return self

    def order(self, col, desc=False, **_k):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        matches = [
            r
            for r in self.table.rows
            if all(r.get(k) == v for k, v in self.filters.items())
            and all(r.get(k) is None for k in self.null_filters)
        ]
        if self._order_col:
            matches = sorted(matches, key=lambda r: r.get(self._order_col) or 0, reverse=getattr(self, "_order_desc", False))
        if self._limit:
            matches = matches[: self._limit]
        if self.op == "select":
            return _FakeResponse(matches)
        if self.op == "update":
            for r in matches:
                r.update(self.payload)
            return _FakeResponse(matches)
        raise AssertionError(f"unsupported op {self.op}")


class _FakeInsertResult:
    def __init__(self, rows):
        self._rows = rows

    def execute(self):
        return _FakeResponse(self._rows)


class _FakeTable:
    def __init__(self, name):
        self.name = name
        self.rows: list[dict] = []

    def select(self, *_a, **_k):
        return _FakeQuery(self, "select")

    def update(self, payload):
        return _FakeQuery(self, "update", payload)

    def insert(self, record):
        items = record if isinstance(record, list) else [record]
        inserted = []
        for item in items:
            row = dict(item)
            row.setdefault("id", str(uuid.uuid4()))
            self.rows.append(row)
            inserted.append(row)
        return _FakeInsertResult(inserted)


class FakeDB:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name))


def _seed_steps(db: FakeDB, state: str, procedure: str, n: int) -> list[str]:
    ids = []
    for i in range(1, n + 1):
        row = db.table("rera_guides").insert(
            {
                "state": state,
                "procedure": procedure,
                "step_no": i,
                "instruction": f"Step {i} instruction",
                "required_documents": [],
                "verification_status": "verified",
                "source_url": "https://rera.example.gov.in",
                "last_verified": "2026-08-01",
            }
        ).execute().data[0]
        ids.append(row["id"])
    return ids


def _seed_matter(db: FakeDB, user_id: str, module: str = "rera") -> str:
    row = db.table("matters").insert(
        {"user_id": user_id, "title": "Test RERA Matter", "module": module}
    ).execute().data[0]
    return row["id"]


def _make_client(fake_db, user_id="user-1"):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id, email="nitesh@example.com", db=fake_db
    )
    return TestClient(app)


AUTH = {"Authorization": "Bearer test-token"}


# --- Domain: state/procedure/step resolution --------------------------------


def test_list_procedures_returns_curated_procedures_only():
    db = FakeDB()
    _seed_steps(db, "Delhi", "project-registration", 3)
    _seed_steps(db, "Delhi", "complaint-filing", 2)
    result = rera.list_procedures("Delhi", db)
    by_name = {r["procedure"]: r["step_count"] for r in result}
    assert by_name == {"project-registration": 3, "complaint-filing": 2}


def test_list_procedures_rejects_unsupported_state():
    db = FakeDB()
    with pytest.raises(rera.RERAError):
        rera.list_procedures("Karnataka", db)


def test_walkthrough_steps_ordered_by_step_no():
    db = FakeDB()
    _seed_steps(db, "Maharashtra", "project-registration", 4)
    steps = rera.list_walkthrough_steps("Maharashtra", "project-registration", db)
    assert [s["step_no"] for s in steps] == [1, 2, 3, 4]


def test_walkthrough_steps_empty_when_uncurated():
    db = FakeDB()
    steps = rera.list_walkthrough_steps("Delhi", "nonexistent-procedure", db)
    assert steps == []


# --- Domain: walkthrough progress -------------------------------------------


def test_progress_none_when_never_started():
    db = FakeDB()
    _seed_steps(db, "Delhi", "project-registration", 3)
    assert rera.get_progress("user-1", "Delhi", "project-registration", None, db) is None


def test_progress_create_then_mark_step_complete():
    db = FakeDB()
    step_ids = _seed_steps(db, "Delhi", "project-registration", 3)

    row = rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, step_ids[0], None, db)
    assert row["completed_step_ids"] == [step_ids[0]]
    assert row["is_complete"] is False

    row = rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, step_ids[1], None, db)
    assert set(row["completed_step_ids"]) == {step_ids[0], step_ids[1]}

    row = rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, step_ids[2], None, db)
    assert row["is_complete"] is True
    # Exactly one progress row exists for this (user, state, procedure) —
    # confirms upsert, not insert-every-time.
    assert len(db.table("rera_walkthrough_progress").rows) == 1


def test_progress_mark_step_incomplete_reverts_completion():
    db = FakeDB()
    step_ids = _seed_steps(db, "Delhi", "project-registration", 2)
    rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, step_ids[0], None, db)
    rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, step_ids[1], None, db)
    row = rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, None, step_ids[0], db)
    assert row["completed_step_ids"] == [step_ids[1]]
    assert row["is_complete"] is False


def test_progress_rejects_unknown_step_id():
    db = FakeDB()
    _seed_steps(db, "Delhi", "project-registration", 2)
    with pytest.raises(rera.RERAError):
        rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, str(uuid.uuid4()), None, db)


def test_progress_rejects_current_step_out_of_range():
    db = FakeDB()
    _seed_steps(db, "Delhi", "project-registration", 2)
    with pytest.raises(rera.RERAError):
        rera.upsert_progress("user-1", "Delhi", "project-registration", None, 99, None, None, db)


def test_progress_rejects_procedure_with_no_curated_steps():
    db = FakeDB()
    with pytest.raises(rera.RERAError):
        rera.upsert_progress("user-1", "Delhi", "ghost-procedure", None, 1, None, None, db)


def test_progress_rejects_unsupported_state():
    db = FakeDB()
    with pytest.raises(rera.RERAError):
        rera.upsert_progress("user-1", "Karnataka", "project-registration", None, 1, None, None, db)


def test_progress_matter_scoping_independent_of_global():
    """A user can have both a global (no matter) progress and a
    matter-scoped progress for the SAME state+procedure, as two distinct
    rows — this is the deliberate product decision (migration 0019's
    docstring): walkthrough progress is not forced into the matter model."""
    db = FakeDB()
    step_ids = _seed_steps(db, "Delhi", "project-registration", 2)
    matter_id = _seed_matter(db, "user-1", module="rera")

    global_row = rera.upsert_progress("user-1", "Delhi", "project-registration", None, None, step_ids[0], None, db)
    matter_row = rera.upsert_progress("user-1", "Delhi", "project-registration", matter_id, None, step_ids[1], None, db)

    assert global_row["id"] != matter_row["id"]
    assert global_row["matter_id"] is None
    assert matter_row["matter_id"] == matter_id
    assert global_row["completed_step_ids"] == [step_ids[0]]
    assert matter_row["completed_step_ids"] == [step_ids[1]]


def test_progress_rejects_non_rera_matter():
    db = FakeDB()
    _seed_steps(db, "Delhi", "project-registration", 2)
    litigation_matter_id = _seed_matter(db, "user-1", module="litigation")
    with pytest.raises(rera.RERAError):
        rera.upsert_progress("user-1", "Delhi", "project-registration", litigation_matter_id, 1, None, None, db)


def test_progress_rejects_matter_belonging_to_nobody():
    db = FakeDB()
    _seed_steps(db, "Delhi", "project-registration", 2)
    with pytest.raises(rera.RERAError):
        rera.upsert_progress("user-1", "Delhi", "project-registration", str(uuid.uuid4()), 1, None, None, db)


# --- API: authentication / authorization / HTTP wiring -----------------------


def test_states_endpoint_requires_auth():
    client = TestClient(app)
    resp = client.get("/api/rera/states")
    assert resp.status_code in (401, 422)


def test_states_endpoint_returns_phase1_states():
    db = FakeDB()
    client = _make_client(db)
    try:
        resp = client.get("/api/rera/states", headers=AUTH)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == ["Delhi", "Maharashtra", "Uttar Pradesh"]


def test_procedures_endpoint_400_for_unsupported_state():
    db = FakeDB()
    client = _make_client(db)
    try:
        resp = client.get("/api/rera/procedures", params={"state": "Karnataka"}, headers=AUTH)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


def test_walkthrough_progress_put_and_get_roundtrip():
    db = FakeDB()
    step_ids = _seed_steps(db, "Delhi", "project-registration", 2)
    client = _make_client(db)
    try:
        put_resp = client.put(
            "/api/rera/walkthrough/Delhi/project-registration/progress",
            json={"mark_step_complete_id": step_ids[0]},
            headers=AUTH,
        )
        get_resp = client.get(
            "/api/rera/walkthrough/Delhi/project-registration/progress",
            headers=AUTH,
        )
    finally:
        app.dependency_overrides.clear()

    assert put_resp.status_code == 200
    assert put_resp.json()["completed_step_ids"] == [step_ids[0]]
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == put_resp.json()["id"]


# --- Security: cross-user isolation ------------------------------------------


def test_progress_write_is_stamped_with_the_authenticated_users_id():
    """IMPORTANT SCOPE NOTE, not just a docstring: rera_walkthrough_progress
    is owned directly by user_id (not matter-derived), and — exactly like
    `matters` itself (see app/services/matters.py::list_matters, which
    issues no explicit .eq("user_id", ...) filter at all) — this project's
    established convention is to rely ENTIRELY on Postgres RLS
    (rera_walkthrough_progress_owner_all, migration 0019:
    `user_id = auth.uid()`) for cross-user isolation, not an
    application-layer filter. That means TRUE cross-user read/write
    isolation cannot be proven against a FakeDB, which has no RLS
    concept at all — it can only be verified against a live Supabase
    instance with RLS active (see
    docs/30_Implementation/RERA_BACKEND_INTEGRATION_CONTRACT.md's Runtime
    Verification section for that check, and Security Testing Status for
    this exact limitation stated plainly, not glossed over).

    What THIS test proves, honestly: the row a request writes is stamped
    with the requesting user's own id (never a caller-suppliable value —
    `user_id` is not a field on RERAWalkthroughProgressUpdate at all, so
    it cannot be spoofed from the request body), which is the
    precondition RLS's `user_id = auth.uid()` policy depends on being
    true."""
    db = FakeDB()
    step_ids = _seed_steps(db, "Delhi", "project-registration", 2)

    client_a = _make_client(db, user_id="user-A")
    try:
        resp = client_a.put(
            "/api/rera/walkthrough/Delhi/project-registration/progress",
            json={"mark_step_complete_id": step_ids[0]},
            headers=AUTH,
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["user_id"] == "user-A"
    assert db.table("rera_walkthrough_progress").rows[0]["user_id"] == "user-A"


# --- Validation edge cases ----------------------------------------------------


def test_malformed_matter_id_fails_closed():
    db = FakeDB()
    _seed_steps(db, "Delhi", "project-registration", 1)
    with pytest.raises(rera.RERAError):
        rera.upsert_progress("user-1", "Delhi", "project-registration", "not-a-uuid", 1, None, None, db)
