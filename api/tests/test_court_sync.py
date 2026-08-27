"""Tests for app/services/court_sync.py -- the eCourts sync orchestration.
Mocks CourtDataGateway entirely (no network) and exercises the real
upsert/idempotency/manual-override/org-access logic against a fake
Supabase client (reusing test_platform.py's FakeServiceClient)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services import court_sync
from app.services.court_data_gateway import CourtDataGatewayError
from tests.test_platform import FakeServiceClient, _org


@dataclass
class _FakeCaseDetail:
    cnr: str
    court_name: str | None = "Test Court"
    judge: str | None = "J. Test"
    status: str | None = "Pending"
    petitioners: list = None
    respondents: list = None
    raw: dict = None

    def __post_init__(self):
        self.petitioners = self.petitioners or []
        self.respondents = self.respondents or []
        self.raw = self.raw if self.raw is not None else {"cnr": self.cnr}


@dataclass
class _FakeCauselistEntry:
    cnr: str
    has_causelist: bool
    court: str | None = "Court Hall 4"
    court_type: str | None = None
    list_type: str | None = None
    listing_for: str | None = None
    bench: str | None = "Bench A"
    court_no: str | None = "4"
    date: str | None = "2026-08-28"
    raw: dict = None

    def __post_init__(self):
        self.raw = self.raw if self.raw is not None else {}


class _FakeGateway:
    def __init__(self, case_detail=None, causelist=None, case_lookup_raises=None, causelist_raises=None):
        self._case_detail = case_detail
        self._causelist = causelist or {}
        self._case_lookup_raises = case_lookup_raises
        self._causelist_raises = causelist_raises
        self.case_lookup_calls: list[str] = []
        self.causelist_calls: list[list[str]] = []

    def case_lookup(self, cnr):
        self.case_lookup_calls.append(cnr)
        if self._case_lookup_raises:
            raise self._case_lookup_raises
        return self._case_detail

    def causelist_batch(self, cnrs):
        self.causelist_calls.append(cnrs)
        if self._causelist_raises:
            raise self._causelist_raises
        return self._causelist


def _matter(id_="m1", organization_id="org-1", user_id="u1", title="Test Matter"):
    return {"id": id_, "organization_id": organization_id, "user_id": user_id, "title": title, "case_number_formatted": None}


def _tracking(matter_id="m1", cnr="CNR1", enabled=True):
    return {"id": "track-1", "matter_id": matter_id, "cnr_number": cnr, "tracking_enabled": enabled}


def _base_fake(*, org_status="active", access_enabled=True, tracking=None, matter=None, hearings=None):
    return FakeServiceClient(
        {
            "court_case_tracking": [tracking] if tracking else [],
            "matters": [matter] if matter else [_matter()],
            "organizations": [_org("org-1", status=org_status, access_enabled=access_enabled)],
            "hearings": list(hearings or []),
            "court_sync_log": [],
            "notifications": [],
        }
    )


def test_tracking_not_enabled_raises_skipped(monkeypatch):
    fake = _base_fake(tracking=_tracking(enabled=False))
    with pytest.raises(court_sync.CourtSyncSkipped, match="tracking not enabled"):
        court_sync.sync_matter_court_data("m1", fake)


def test_no_cnr_raises_skipped(monkeypatch):
    fake = _base_fake(tracking=_tracking(cnr=None))
    with pytest.raises(court_sync.CourtSyncSkipped, match="no CNR"):
        court_sync.sync_matter_court_data("m1", fake)


def test_suspended_org_raises_skipped_and_makes_no_gateway_call(monkeypatch):
    fake = _base_fake(org_status="suspended", tracking=_tracking())
    gateway = _FakeGateway()
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    with pytest.raises(court_sync.CourtSyncSkipped, match="access is not active"):
        court_sync.sync_matter_court_data("m1", fake)
    assert gateway.case_lookup_calls == []
    assert gateway.causelist_calls == []


def test_expired_org_raises_skipped(monkeypatch):
    fake = _base_fake(org_status="expired", tracking=_tracking())
    gateway = _FakeGateway()
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)
    with pytest.raises(court_sync.CourtSyncSkipped):
        court_sync.sync_matter_court_data("m1", fake)


def test_access_disabled_raises_skipped_even_if_status_active(monkeypatch):
    fake = _base_fake(org_status="active", access_enabled=False, tracking=_tracking())
    gateway = _FakeGateway()
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)
    with pytest.raises(court_sync.CourtSyncSkipped):
        court_sync.sync_matter_court_data("m1", fake)


def test_successful_sync_creates_hearing_and_notification(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1", raw={"cnr": "CNR1", "status": "Pending"}),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=True)},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    result = court_sync.sync_matter_court_data("m1", fake)

    assert result["status"] == "synced"
    assert result["hearing_created"] is True
    assert gateway.case_lookup_calls == ["CNR1"]
    assert gateway.causelist_calls == [["CNR1"]]

    tracking_row = fake.table("court_case_tracking").rows[0]
    assert tracking_row["sync_status"] == "synced"
    assert tracking_row["last_error"] is None
    assert tracking_row["provider_metadata"] == {"cnr": "CNR1", "status": "Pending"}

    hearings = fake.table("hearings").rows
    assert len(hearings) == 1
    assert hearings[0]["court"] == "Court Hall 4"
    assert hearings[0]["bench"] == "Bench A"
    assert hearings[0]["item_no"] == "4"
    assert hearings[0]["source"] == "ecourts"

    notifications = fake.table("notifications").rows
    assert len(notifications) == 1
    assert notifications[0]["type"] == "hearing_listed"


def test_repeat_sync_updates_same_hearing_no_duplicate(monkeypatch):
    existing_hearing = {
        "id": "h1", "matter_id": "m1", "organization_id": "org-1", "user_id": "u1",
        "title": "Hearing — Test Matter", "hearing_at": "2026-08-28T00:00:00+00:00",
        "source": "ecourts", "court": "Old Court", "bench": "Old Bench", "item_no": "1",
    }
    fake = _base_fake(tracking=_tracking(), hearings=[existing_hearing])
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1"),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=True, court="New Court", bench="New Bench", court_no="9")},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    result = court_sync.sync_matter_court_data("m1", fake)

    assert result["hearing_created"] is False
    hearings = fake.table("hearings").rows
    assert len(hearings) == 1  # never duplicated
    assert hearings[0]["id"] == "h1"
    assert hearings[0]["court"] == "New Court"
    assert hearings[0]["bench"] == "New Bench"


def test_manual_override_hearing_is_never_touched(monkeypatch):
    override_hearing = {
        "id": "h1", "matter_id": "m1", "organization_id": "org-1", "user_id": "u1",
        "title": "Hearing — Test Matter", "hearing_at": "2026-08-28T00:00:00+00:00",
        "source": "manual_override", "court": "Lawyer-corrected Court", "bench": "Lawyer-corrected Bench", "item_no": "7",
    }
    fake = _base_fake(tracking=_tracking(), hearings=[override_hearing])
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1"),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=True, court="Provider Court", bench="Provider Bench")},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    result = court_sync.sync_matter_court_data("m1", fake)

    assert result["hearing_id"] is None  # sync deliberately did not touch it
    hearings = fake.table("hearings").rows
    assert len(hearings) == 1
    assert hearings[0]["court"] == "Lawyer-corrected Court"  # untouched
    assert hearings[0]["bench"] == "Lawyer-corrected Bench"
    # No notification for a hearing sync skipped due to override.
    assert fake.table("notifications").rows == []


def test_case_lookup_failure_sets_error_state_and_logs(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(case_lookup_raises=CourtDataGatewayError("simulated provider failure, request_id=abc"))
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    with pytest.raises(CourtDataGatewayError):
        court_sync.sync_matter_court_data("m1", fake)

    tracking_row = fake.table("court_case_tracking").rows[0]
    assert tracking_row["sync_status"] == "error"
    assert tracking_row["last_error"] == "Case lookup failed. See sync log for detail."  # generic, not raw provider text

    log_rows = fake.table("court_sync_log").rows
    assert any(r["operation"] == "case_lookup" and r["status"] == "error" for r in log_rows)


def test_causelist_failure_does_not_invalidate_successful_case_lookup(monkeypatch):
    """A causelist_batch failure is logged but must not discard the
    case_lookup result we already have -- partial success, not total failure."""
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1"),
        causelist_raises=CourtDataGatewayError("simulated causelist failure"),
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    result = court_sync.sync_matter_court_data("m1", fake)

    assert result["status"] == "synced"
    tracking_row = fake.table("court_case_tracking").rows[0]
    assert tracking_row["sync_status"] == "synced"
    log_rows = fake.table("court_sync_log").rows
    assert any(r["operation"] == "causelist_batch" and r["status"] == "error" for r in log_rows)
    assert any(r["operation"] == "case_lookup" and r["status"] == "success" for r in log_rows)


def test_no_causelist_entry_no_hearing_created(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(case_detail=_FakeCaseDetail(cnr="CNR1"), causelist={})
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    result = court_sync.sync_matter_court_data("m1", fake)
    assert result["hearing_id"] is None
    assert fake.table("hearings").rows == []
