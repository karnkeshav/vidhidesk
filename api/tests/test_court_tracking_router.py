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
from app.services.court_data_gateway import (
    CaseSearchItem,
    CaseSearchResult,
    CourtCaseDetail,
    CourtDataGatewayError,
    CourtDataNotConfiguredError,
    CourtDataNotFoundError,
    CourtDataQuotaExceededError,
)
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
        self._in_filters: dict[str, list] = {}
        self._order_col = None

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def in_(self, col, vals):
        self._in_filters[col] = list(vals)
        return self

    def order(self, col, desc=False):
        self._order_col = (col, desc)
        return self

    def limit(self, _n):
        return self

    def select(self, *_a, **_k):
        return self

    def execute(self):
        if self.op == "select":
            matches = [
                r
                for r in self.table.rows
                if all(r.get(k) == v for k, v in self.filters.items())
                and all(r.get(k) in v for k, v in self._in_filters.items())
            ]
            if self._order_col:
                col, desc = self._order_col
                matches = sorted(matches, key=lambda r: r[col], reverse=desc)
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
    def __init__(self, matters=None, tracking=None, **extra_tables):
        self._tables = {
            "matters": _FakeTable("matters", matters or []),
            "court_case_tracking": _FakeTable("court_case_tracking", tracking or []),
        }
        for name, rows in extra_tables.items():
            self._tables[name] = _FakeTable(name, rows)

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


@pytest.fixture(autouse=True)
def _allow_ecourts_search(monkeypatch):
    """Every existing test in this file predates the eCourts search
    allowlist gate (2026-09-11) and exercises the underlying tracking/
    sync/search behavior, not the gate itself -- default every test to
    "allowed" so they keep testing what they always tested. The gate's
    own allow/deny behavior is covered separately below
    (test_ecourts_search_gate.py)."""
    monkeypatch.setattr(court_tracking_router, "is_ecourts_search_allowed", lambda email: True)


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


def test_update_tracking_cnr_change_clears_stale_typed_fields():
    existing_tracking = {
        "id": "t1", "matter_id": "m1", "cnr_number": "OLDCNR", "tracking_enabled": True,
        "sync_status": "synced", "last_error": None, "last_synced_at": "2026-08-01T00:00:00Z",
        "next_hearing_date": "2026-08-12", "provider_metadata": {"cnr": "OLDCNR"},
        "court_name": "Old Court", "judge": "J. Old", "case_status": "Pending",
        "petitioners": ["Old Petitioner"], "respondents": ["Old Respondent"],
        "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z",
    }
    db = FakeDB(matters=[_matter_row()], tracking=[existing_tracking])
    client = _client_with(db)
    try:
        resp = client.patch(
            "/api/matters/m1/court-tracking",
            json={"cnr_number": "NEWCNR123"},
            headers={"Authorization": "Bearer x"},
        )
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["cnr_number"] == "NEWCNR123"
    assert body["court_name"] is None
    assert body["judge"] is None
    assert body["case_status"] is None
    assert body["petitioners"] == []
    assert body["respondents"] == []
    assert body["provider_metadata"] is None
    assert body["next_hearing_date"] is None


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


def test_trigger_sync_cnr_not_found_returns_400_not_502(monkeypatch):
    """A 404 from the provider means the CNR itself wasn't found -- a
    client error, not a connectivity/outage problem. Found in production
    (2026-09-07): this used to return the same 502 "unable to reach the
    provider" as a real outage, which is actively wrong for a bad CNR."""
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

    class _NotFoundGateway:
        def case_lookup(self, cnr):
            raise CourtDataNotFoundError("eCourts API returned 404 (request_id=abc)")

    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: _NotFoundGateway())

    client = _client_with(db)
    try:
        resp = client.post("/api/matters/m1/court-tracking/sync", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()

    tracking_row = fake_sc.table("court_case_tracking").rows[0]
    assert tracking_row["last_error"] == "CNR not found on eCourts. Double-check the CNR and try again."


def test_trigger_sync_quota_exceeded_returns_402_not_502(monkeypatch):
    """A 402 from the provider means the eCourts account's own quota/
    billing needs attention -- found in production (2026-09-07) right
    after a burst of testing calls exhausted a real account's quota. Same
    conflation-with-502 bug as the 404 case, different root cause."""
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

    class _QuotaExceededGateway:
        def case_lookup(self, cnr):
            raise CourtDataQuotaExceededError("eCourts API returned 402 (request_id=abc)")

    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: _QuotaExceededGateway())

    client = _client_with(db)
    try:
        resp = client.post("/api/matters/m1/court-tracking/sync", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 402
    assert "quota" in resp.json()["detail"].lower()

    tracking_row = fake_sc.table("court_case_tracking").rows[0]
    assert "quota/billing" in tracking_row["last_error"]


def test_search_court_cases_requires_a_filter():
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-search", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400


def test_search_court_cases_not_configured_returns_501(monkeypatch):
    monkeypatch.setattr(
        court_tracking_router,
        "CourtDataGateway",
        lambda: (_ for _ in ()).throw(CourtDataNotConfiguredError("no key")),
    )
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-search?query=test", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 501


def test_search_court_cases_provider_error_returns_502(monkeypatch):
    class _ExplodingGateway:
        def case_search(self, **_kwargs):
            raise CourtDataGatewayError("secret internal provider detail")

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _ExplodingGateway())
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-search?query=test", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 502
    assert "secret internal provider detail" not in resp.text


def test_search_court_cases_returns_items(monkeypatch):
    class _FakeGateway:
        def case_search(self, **kwargs):
            assert kwargs["advocates"] == ["Sharma"]
            return CaseSearchResult(
                items=[
                    CaseSearchItem(
                        cnr="DLND020047882015",
                        case_number="CS 1/2026",
                        court_name="Delhi HC",
                        case_type="WP_C",
                        status="Pending",
                        petitioners=["A"],
                        respondents=["B"],
                        advocates=["Sharma"],
                        raw={},
                    )
                ],
                total=1,
                has_next_page=False,
                request_id="req-1",
                raw={},
            )

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _FakeGateway())
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-search?advocates=Sharma", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["cnr"] == "DLND020047882015"
    assert body["items"][0]["advocates"] == ["Sharma"]


def test_preview_court_case_requires_a_cnr():
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-lookup-preview?cnr=", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400


def test_preview_court_case_not_configured_returns_501(monkeypatch):
    monkeypatch.setattr(
        court_tracking_router,
        "CourtDataGateway",
        lambda: (_ for _ in ()).throw(CourtDataNotConfiguredError("no key")),
    )
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-lookup-preview?cnr=DLND020047882015", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 501


def test_preview_court_case_provider_error_returns_502(monkeypatch):
    class _ExplodingGateway:
        def case_lookup(self, _cnr):
            raise CourtDataGatewayError("secret internal provider detail")

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _ExplodingGateway())
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-lookup-preview?cnr=DLND020047882015", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 502
    assert "secret internal provider detail" not in resp.text


def test_preview_court_case_returns_detail_and_persists_nothing():
    class _FakeGateway:
        def case_lookup(self, cnr):
            assert cnr == "DLHC010163362026"
            return CourtCaseDetail(
                cnr=cnr,
                court_name="Delhi High Court",
                judge="ANUP JAIRAM BHAMBHANI",
                judges=["ANUP JAIRAM BHAMBHANI"],
                status="PENDING",
                petitioners=["Deepak"],
                respondents=["State (nct of Delhi)"],
                petitioner_advocates=["AJAY KUMAR YADAV"],
                respondent_advocates=[],
                interlocutory_applications=[],
                next_hearing_date=None,
                raw={},
            )

    fake_db = FakeDB()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(court_tracking_router, "CourtDataGateway", lambda: _FakeGateway())
        client = _client_with(fake_db)
        try:
            resp = client.get(
                "/api/court-lookup-preview?cnr=DLHC010163362026", headers={"Authorization": "Bearer x"}
            )
        finally:
            _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["cnr"] == "DLHC010163362026"
    assert body["petitioners"] == ["Deepak"]
    assert body["respondents"] == ["State (nct of Delhi)"]
    # The whole point of a preview: no court_case_tracking row is
    # created/touched by looking one up, only by the follow-up PATCH.
    assert fake_db._tables["court_case_tracking"].rows == []


def test_preview_court_case_cnr_not_found_returns_400_not_502(monkeypatch):
    """Same bug class as test_trigger_sync_cnr_not_found_returns_400_not_502,
    different endpoint: CourtDataNotFoundError is a CourtDataGatewayError
    subclass, so without its own except clause here it fell through to the
    generic 502 -- found in production (2026-09-07) via a real search-step
    lookup that should have been a clean "CNR not found", not an "outage"."""
    class _NotFoundGateway:
        def case_lookup(self, _cnr):
            raise CourtDataNotFoundError("eCourts API returned 404 (request_id=abc)")

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _NotFoundGateway())
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-lookup-preview?cnr=DLND020047882015", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


def test_preview_court_case_quota_exceeded_returns_402_not_502(monkeypatch):
    class _QuotaExceededGateway:
        def case_lookup(self, _cnr):
            raise CourtDataQuotaExceededError("eCourts API returned 402 (request_id=abc)")

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _QuotaExceededGateway())
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-lookup-preview?cnr=DLND020047882015", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 402
    assert "quota" in resp.json()["detail"].lower()


def test_search_court_cases_cnr_not_found_returns_400_not_502(monkeypatch):
    """Same gap, third endpoint: case_search() shares CourtDataGateway._
    request() with case_lookup(), so it can raise the same 404/402 subclasses."""
    class _NotFoundGateway:
        def case_search(self, **_kwargs):
            raise CourtDataNotFoundError("eCourts API returned 404 (request_id=abc)")

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _NotFoundGateway())
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-search?query=test", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 400


def test_search_court_cases_quota_exceeded_returns_402_not_502(monkeypatch):
    class _QuotaExceededGateway:
        def case_search(self, **_kwargs):
            raise CourtDataQuotaExceededError("eCourts API returned 402 (request_id=abc)")

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _QuotaExceededGateway())
    client = _client_with(FakeDB())
    try:
        resp = client.get("/api/court-search?query=test", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 402


def test_preview_uses_cached_data_instead_of_calling_the_live_api(monkeypatch):
    """Cache-first (2026-09-07, real user request): if this exact CNR was
    already synced on one of the caller's own matters, reuse that instead
    of burning eCourts quota on an identical live call."""
    cached_row = {
        "id": "t1", "matter_id": "m1", "cnr_number": "DLHC010163362026",
        "court_name": "DLHC", "judge": "ANUP JAIRAM BHAMBHANI", "case_status": "PENDING",
        "petitioners": ["Deepak"], "respondents": ["State (nct of Delhi)"],
        "provider_metadata": {"cnr": "DLHC010163362026"}, "last_synced_at": "2026-09-07T02:30:00Z",
    }
    db = FakeDB(matters=[_matter_row()], tracking=[cached_row])

    def _explode():
        raise AssertionError("live gateway must not be called on a cache hit")

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", _explode)
    client = _client_with(db)
    try:
        resp = client.get(
            "/api/court-lookup-preview?cnr=DLHC010163362026", headers={"Authorization": "Bearer x"}
        )
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert body["court_name"] == "DLHC"
    assert body["judge"] == "ANUP JAIRAM BHAMBHANI"
    assert body["status"] == "PENDING"
    assert body["petitioners"] == ["Deepak"]


def test_preview_ignores_tracking_row_never_actually_synced(monkeypatch):
    """A tracking row can exist (CNR saved) with provider_metadata still
    null (never synced, or sync errored) -- that's not a cache hit, and
    must still fall through to the live API."""
    unsynced_row = {
        "id": "t1", "matter_id": "m1", "cnr_number": "DLHC010163362026",
        "court_name": None, "judge": None, "case_status": None,
        "petitioners": [], "respondents": [], "provider_metadata": None, "last_synced_at": None,
    }
    db = FakeDB(matters=[_matter_row()], tracking=[unsynced_row])

    class _FakeGateway:
        def case_lookup(self, cnr):
            return CourtCaseDetail(
                cnr=cnr, court_name="Delhi High Court", judge="ANUP JAIRAM BHAMBHANI",
                judges=["ANUP JAIRAM BHAMBHANI"], status="PENDING", petitioners=["Deepak"],
                respondents=["State (nct of Delhi)"], petitioner_advocates=[], respondent_advocates=[],
                interlocutory_applications=[], next_hearing_date=None, raw={},
            )

    monkeypatch.setattr(court_tracking_router, "CourtDataGateway", lambda: _FakeGateway())
    client = _client_with(db)
    try:
        resp = client.get(
            "/api/court-lookup-preview?cnr=DLHC010163362026", headers={"Authorization": "Bearer x"}
        )
    finally:
        _teardown()
    assert resp.status_code == 200
    assert resp.json()["court_name"] == "Delhi High Court"  # came from the live call, not the null row


def test_list_causelist_returns_rows_newest_first():
    causelist_rows = [
        {
            "id": "c1", "matter_id": "m1", "cnr_number": "CNR1", "hearing_date": "2026-08-20",
            "hearing_time": None, "bench_number": "Bench A", "judge_names": ["J. Test"],
            "court_location": "Court Hall 4", "causelist_type": None, "fetched_at": "2026-08-20T00:00:00Z",
        },
        {
            "id": "c2", "matter_id": "m1", "cnr_number": "CNR1", "hearing_date": "2026-09-08",
            "hearing_time": None, "bench_number": "Bench B", "judge_names": None,
            "court_location": "Court Hall 4", "causelist_type": None, "fetched_at": "2026-09-01T00:00:00Z",
        },
    ]
    db = FakeDB(matters=[_matter_row()], court_hearings_causelist=causelist_rows)
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/m1/causelist", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert [row["id"] for row in body] == ["c2", "c1"]  # newest hearing_date first


def test_list_causelist_404s_for_unknown_matter():
    db = FakeDB(matters=[])
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/missing/causelist", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 404


def test_list_interlocutory_applications_empty_by_default():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/m1/interlocutory-applications", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_case_advocates_joins_links_to_advocates():
    links = [
        {"id": "l1", "matter_id": "m1", "advocate_id": "a1", "role": "PETITIONER_COUNSEL",
         "first_appeared": "2026-01-01", "last_appeared": "2026-06-01"},
    ]
    advocates = [
        {"id": "a1", "name": "R. Sharma", "bar_council_id": "D/1234/2010", "phone": "9999999999",
         "email": None, "office_address": None},
    ]
    db = FakeDB(matters=[_matter_row()], case_advocate_links=links, court_advocates=advocates)
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/m1/case-advocates", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "R. Sharma"
    assert body[0]["role"] == "PETITIONER_COUNSEL"


def test_list_case_advocates_empty_by_default():
    db = FakeDB(matters=[_matter_row()])
    client = _client_with(db)
    try:
        resp = client.get("/api/matters/m1/case-advocates", headers={"Authorization": "Bearer x"})
    finally:
        _teardown()
    assert resp.status_code == 200
    assert resp.json() == []
