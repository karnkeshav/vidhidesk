"""Router-level tests for the Hearing Brief endpoints
(api/app/routers/hearing_briefs.py) -- Iter 5 Gap 2.

Before this file, brief generation/review had ONLY service-level tests
(test_hearing_brief.py, calling app/services/hearing_brief.py functions
directly with a fake db) -- the actual HTTP routes, their auth dependency,
and their own _get_matter_or_404 guard were never exercised end-to-end.
This file closes that gap using the same TestClient/dependency_overrides
pattern already established in test_hearings.py and test_matter_history.py.

IMPORTANT -- what these tests do and do not prove:
These are APPLICATION/ROUTER AUTHORIZATION tests against an in-process
FakeDB. They prove the router's own guards (_get_matter_or_404, the
hearing-belongs-to-matter check inside hearing_brief.py) behave correctly
when reached through the real HTTP routes. They do NOT verify real
Postgres RLS -- a FakeDB cannot simulate row-level security, and "another
organization's user" here is modeled as a second FakeDB instance that
simply never had the first organization's rows written into it (the
same equivalence every other router test in this codebase relies on --
see test_hearings.py's and hearing_briefs.py's own docstrings). Real RLS
behavior against a live database is checked by api/scripts/verify_*.py,
not by this file.

One concrete finding from writing these tests, reported here rather than
silently worked around: review_hearing_brief_endpoint calls
_get_matter_or_404(user, matter_id) but never verifies that brief_id
actually belongs to matter_id, and hearing_brief.review_hearing_brief()
itself updates purely by `.eq("id", brief_id)` with no organization/matter
filter at all. In production this is safe only because user.db is
RLS-scoped -- Postgres silently returns zero rows for a brief outside the
caller's organization, which review_hearing_brief() then reports as "not
found". There is no application-level defense-in-depth here: if user.db
were ever accidentally swapped for a service-role client for this call,
cross-tenant review would succeed silently. This is a real design
observation, not something these tests can prove or disprove with a
FakeDB, since a FakeDB has no RLS to accidentally bypass in the first
place.
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import hearing_brief
from app.services.llm_gateway import GenerationResult


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, op, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: dict[str, object] = {}
        self._order = None
        self._limit = None

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
        if self._order:
            col, desc = self._order
            matches = sorted(matches, key=lambda r: r.get(col) or 0, reverse=desc)
        if self._limit is not None:
            matches = matches[: self._limit]
        if self.op == "select":
            return _FakeResponse(matches)
        if self.op == "update":
            json.dumps(self.payload)
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
        items = record if isinstance(record, list) else [record]
        inserted = []
        for item in items:
            json.dumps(item)  # mirrors the real client's own JSON encoding, same as test_hearings.py
            row = dict(item)
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", "2026-08-30T00:00:00Z")
            row.setdefault("updated_at", "2026-08-30T00:00:00Z")
            self.rows.append(row)
            inserted.append(row)
        return _FakeInsertResult(inserted)


class _FakeInsertResult:
    def __init__(self, rows):
        self._rows = rows

    def execute(self):
        return _FakeResponse(self._rows)


class FakeDB:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name))


def _seed_matter(db, matter_id="m1", organization_id="org-1"):
    db.table("matters").rows.append(
        {"id": matter_id, "organization_id": organization_id, "user_id": "user-1", "title": "Test Matter", "module": "litigation"}
    )


def _seed_hearing(db, hearing_id="h1", matter_id="m1", hearing_at="2026-08-01T10:00:00Z"):
    db.table("hearings").rows.append({"id": hearing_id, "matter_id": matter_id, "hearing_at": hearing_at})


def _seed_brief(db, brief_id="b1", matter_id="m1", hearing_id="h1", organization_id="org-1", version=1, status="draft"):
    row = {
        "id": brief_id,
        "organization_id": organization_id,
        "matter_id": matter_id,
        "hearing_id": hearing_id,
        "version": version,
        "status": status,
        "generated_at": "2026-08-30T00:00:00Z",
        "generated_by": "test/model",
        "source_snapshot": {},
        "brief_content": {
            "case_record": [], "supported_arguments": [], "risk_highlights": [],
            "ai_suggested_points": [], "checklist": [], "information_gaps": [],
        },
        "lawyer_edits": None,
        "reviewed_at": None,
        "approved_at": None,
        "created_at": "2026-08-30T00:00:00Z",
        "updated_at": "2026-08-30T00:00:00Z",
    }
    db.table("hearing_briefs").rows.append(row)
    return row


def _make_client(fake_db, organization_id="org-1"):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="user-1", email="nitesh@example.com", db=fake_db, organization_id=organization_id
    )
    return TestClient(app)


VALID_JSON = """{
  "case_record": [], "supported_arguments": [], "risk_highlights": [],
  "ai_suggested_points": [], "checklist": [], "information_gaps": []
}"""


def _fake_generate_factory(text: str):
    def _fake(prompt, task_type="chat", mask_map=None, entities=None, **kwargs):
        return GenerationResult(text=text, provider="test", model="test-model", latency_ms=1, masked_prompt=prompt)

    return _fake


# --- 1/2/3: authorized organization member happy paths ------------------


def test_authorized_member_can_list_briefs():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_hearing(fake_db)
    _seed_brief(fake_db)
    client = _make_client(fake_db)
    try:
        resp = client.get(
            "/api/matters/m1/hearings/h1/briefs",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == "b1"


def test_authorized_member_can_generate_brief(monkeypatch):
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_hearing(fake_db)
    service_db = FakeDB()  # stands in for service_client() -- pii_masks/notifications only
    monkeypatch.setattr(hearing_brief, "service_client", lambda: service_db)
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory(VALID_JSON))

    client = _make_client(fake_db)
    try:
        resp = client.post(
            "/api/matters/m1/hearings/h1/briefs",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert fake_db.table("hearing_briefs").rows[0]["matter_id"] == "m1"


def test_authorized_member_can_review_brief():
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_hearing(fake_db)
    _seed_brief(fake_db)
    client = _make_client(fake_db)
    try:
        resp = client.patch(
            "/api/matters/m1/briefs/b1/review",
            json={"status": "reviewed"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reviewed"
    assert body["reviewed_at"] is not None


def test_review_brief_persists_lawyer_edits():
    """Iter 5A finding: HearingBriefReviewRequest.lawyer_edits was added
    to fix a real 500 (the frontend always sends this field; the schema
    never declared it, so Pydantic silently dropped it and
    payload.lawyer_edits raised AttributeError), but no test actually sent
    a lawyer_edits payload -- every existing review test omits the field
    entirely, so a future accidental removal of the schema field would
    pass the full suite silently, exactly as it did before this was
    caught. This test closes that gap."""
    fake_db = FakeDB()
    _seed_matter(fake_db)
    _seed_hearing(fake_db)
    _seed_brief(fake_db)
    client = _make_client(fake_db)
    try:
        resp = client.patch(
            "/api/matters/m1/briefs/b1/review",
            json={"status": "reviewed", "lawyer_edits": {"note": "test lawyer edit"}},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["lawyer_edits"] == {"note": "test lawyer edit"}
    assert fake_db.table("hearing_briefs").rows[0]["lawyer_edits"] == {"note": "test lawyer edit"}


# --- 4: nonexistent matter -----------------------------------------------


def test_nonexistent_matter_returns_404_for_list_generate_and_review():
    fake_db = FakeDB()  # no matter seeded at all
    client = _make_client(fake_db)
    try:
        list_resp = client.get("/api/matters/does-not-exist/hearings/h1/briefs", headers={"Authorization": "Bearer test-token"})
        gen_resp = client.post("/api/matters/does-not-exist/hearings/h1/briefs", headers={"Authorization": "Bearer test-token"})
        review_resp = client.patch(
            "/api/matters/does-not-exist/briefs/b1/review",
            json={"status": "reviewed"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert list_resp.status_code == 404
    assert gen_resp.status_code == 404
    assert review_resp.status_code == 404


# --- 5: hearing belonging to another matter ------------------------------


def test_hearing_belonging_to_another_matter_cannot_be_used_to_generate(monkeypatch):
    """m1 exists and is owned by this user; h1 is a real hearing, but it
    belongs to a DIFFERENT matter (m2), not m1. hearing_brief.py's own
    check (hearings.eq('id', hearing_id).eq('matter_id', matter_id)) must
    catch this even though _get_matter_or_404(m1) alone would pass."""
    fake_db = FakeDB()
    _seed_matter(fake_db, matter_id="m1")
    _seed_matter(fake_db, matter_id="m2")
    _seed_hearing(fake_db, hearing_id="h1", matter_id="m2")  # belongs to m2, not m1
    monkeypatch.setattr(hearing_brief, "service_client", lambda: FakeDB())
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory(VALID_JSON))

    client = _make_client(fake_db)
    try:
        resp = client.post(
            "/api/matters/m1/hearings/h1/briefs",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "not found on matter" in resp.json()["detail"]


# --- 6/7: cross-organization isolation -----------------------------------
# Modeled as a second FakeDB that was simply never given org-1's rows --
# the same equivalence real RLS produces (a row outside your organization
# is indistinguishable from one that doesn't exist), not a re-verification
# of RLS itself. See module docstring.


def test_another_organization_cannot_list_briefs():
    org1_db = FakeDB()
    _seed_matter(org1_db, matter_id="m1", organization_id="org-1")
    _seed_hearing(org1_db, hearing_id="h1", matter_id="m1")
    _seed_brief(org1_db, brief_id="b1", matter_id="m1", hearing_id="h1", organization_id="org-1")

    org2_db = FakeDB()  # org-2's own view -- never contains org-1's matter
    client = _make_client(org2_db, organization_id="org-2")
    try:
        resp = client.get("/api/matters/m1/hearings/h1/briefs", headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_another_organization_cannot_generate_brief(monkeypatch):
    org1_db = FakeDB()
    _seed_matter(org1_db, matter_id="m1", organization_id="org-1")
    _seed_hearing(org1_db, hearing_id="h1", matter_id="m1")
    monkeypatch.setattr(hearing_brief, "service_client", lambda: FakeDB())
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory(VALID_JSON))

    org2_db = FakeDB()
    client = _make_client(org2_db, organization_id="org-2")
    try:
        resp = client.post("/api/matters/m1/hearings/h1/briefs", headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_another_organization_cannot_review_brief():
    """org-2's FakeDB has its own matter with the SAME id string ('m1') to
    pass _get_matter_or_404 (a real org-2 user would of course have a
    different real matter id -- the id string itself carries no
    authorization meaning here, only which FakeDB/organization it was
    seeded into does), but brief 'b1' itself was only ever seeded into
    org-1's FakeDB. review_hearing_brief_endpoint has no brief-to-matter
    ownership check of its own (see module docstring) -- what actually
    stops this is that org-2's db simply never has that row, the same way
    RLS would filter it out in production."""
    org1_db = FakeDB()
    _seed_brief(org1_db, brief_id="b1", matter_id="m1", organization_id="org-1")

    org2_db = FakeDB()
    _seed_matter(org2_db, matter_id="m1", organization_id="org-2")
    client = _make_client(org2_db, organization_id="org-2")
    try:
        resp = client.patch(
            "/api/matters/m1/briefs/b1/review",
            json={"status": "reviewed"},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
