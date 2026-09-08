"""Tests for app/services/court_sync.py -- the eCourts sync orchestration.
Mocks CourtDataGateway entirely (no network) and exercises the real
upsert/idempotency/manual-override/org-access logic against a fake
Supabase client (reusing test_platform.py's FakeServiceClient)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services import court_sync
from app.services.court_data_gateway import CourtDataGatewayError, CourtDataNotFoundError, CourtDataQuotaExceededError
from tests.test_platform import FakeServiceClient, _org


@dataclass
class _FakeCaseDetail:
    cnr: str
    court_name: str | None = "Test Court"
    judge: str | None = "J. Test"
    judges: list = None
    status: str | None = "Pending"
    petitioners: list = None
    respondents: list = None
    petitioner_advocates: list = None
    respondent_advocates: list = None
    interlocutory_applications: list = None
    interim_orders: list = None
    filed_documents: list = None
    next_hearing_date: str | None = None
    raw: dict = None

    def __post_init__(self):
        self.judges = self.judges if self.judges is not None else (["J. Test"] if self.judge else [])
        self.petitioners = self.petitioners or []
        self.respondents = self.respondents or []
        self.petitioner_advocates = self.petitioner_advocates or []
        self.respondent_advocates = self.respondent_advocates or []
        self.interlocutory_applications = self.interlocutory_applications or []
        self.interim_orders = self.interim_orders or []
        self.filed_documents = self.filed_documents or []
        self.raw = self.raw if self.raw is not None else {"cnr": self.cnr}


@dataclass
class _FakeIAEntry:
    application_number: str
    filed_by: str
    filing_date: str
    status_raw: str
    raw: dict = None

    def __post_init__(self):
        self.raw = self.raw if self.raw is not None else {}


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
            "court_hearings_causelist": [],
            "court_advocates": [],
            "case_advocate_links": [],
            "interlocutory_applications": [],
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
    assert tracking_row["court_name"] == "Test Court"
    assert tracking_row["judge"] == "J. Test"
    assert tracking_row["case_status"] == "Pending"
    assert tracking_row["next_hearing_date"] == "2026-08-28"

    hearings = fake.table("hearings").rows
    assert len(hearings) == 1
    assert hearings[0]["court"] == "Court Hall 4"
    assert hearings[0]["bench"] == "Bench A"
    assert hearings[0]["item_no"] == "4"
    assert hearings[0]["source"] == "ecourts"

    notifications = fake.table("notifications").rows
    assert len(notifications) == 1
    assert notifications[0]["type"] == "hearing_listed"

    causelist_rows = fake.table("court_hearings_causelist").rows
    assert len(causelist_rows) == 1
    assert causelist_rows[0]["matter_id"] == "m1"
    assert causelist_rows[0]["hearing_date"] == "2026-08-28"
    assert causelist_rows[0]["bench_number"] == "Bench A"
    assert causelist_rows[0]["court_location"] == "Court Hall 4"
    assert causelist_rows[0]["judge_names"] == ["J. Test"]


def test_repeat_sync_updates_same_causelist_row_no_duplicate(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1", judges=["J. First"]),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=True, court="Court A", bench="Bench A")},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)
    court_sync.sync_matter_court_data("m1", fake)

    gateway2 = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1", judges=["J. Second"]),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=True, court="Court B", bench="Bench B")},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway2)
    court_sync.sync_matter_court_data("m1", fake)

    causelist_rows = fake.table("court_hearings_causelist").rows
    assert len(causelist_rows) == 1  # never duplicated
    assert causelist_rows[0]["court_location"] == "Court B"
    assert causelist_rows[0]["bench_number"] == "Bench B"
    assert causelist_rows[0]["judge_names"] == ["J. Second"]


def test_no_causelist_entry_no_causelist_row(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(case_detail=_FakeCaseDetail(cnr="CNR1"), causelist={})
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    court_sync.sync_matter_court_data("m1", fake)
    assert fake.table("court_hearings_causelist").rows == []
    assert fake.table("court_case_tracking").rows[0]["next_hearing_date"] is None


def test_next_hearing_date_falls_back_to_case_detail_when_no_causelist_listing(monkeypatch):
    """A real end-to-end run (2026-09-07) showed causelist_batch returns
    hasCauselist=false far more often than not -- courtCaseData's own
    nextHearingDate is what keeps this column populated in that common case."""
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1", next_hearing_date="2026-08-12"),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=False, date=None)},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    court_sync.sync_matter_court_data("m1", fake)
    assert fake.table("court_case_tracking").rows[0]["next_hearing_date"] == "2026-08-12"


def test_next_hearing_date_prefers_causelist_over_case_detail(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1", next_hearing_date="2026-08-12"),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=True, date="2026-09-01")},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    court_sync.sync_matter_court_data("m1", fake)
    assert fake.table("court_case_tracking").rows[0]["next_hearing_date"] == "2026-09-01"


def test_sync_creates_advocates_and_links(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(
            cnr="CNR1",
            petitioner_advocates=["Ajay Kumar Yadav"],
            respondent_advocates=["State Counsel"],
        ),
        causelist={},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    court_sync.sync_matter_court_data("m1", fake)

    advocates = fake.table("court_advocates").rows
    assert {a["name"] for a in advocates} == {"Ajay Kumar Yadav", "State Counsel"}
    assert all(a["case_count"] == 1 for a in advocates)

    links = fake.table("case_advocate_links").rows
    assert len(links) == 2
    roles_by_name = {
        next(a["name"] for a in advocates if a["id"] == link["advocate_id"]): link["role"] for link in links
    }
    assert roles_by_name == {"Ajay Kumar Yadav": "PETITIONER_COUNSEL", "State Counsel": "RESPONDENT_COUNSEL"}


def test_sync_reuses_existing_advocate_and_increments_case_count(monkeypatch):
    existing_advocate = {"id": "adv-1", "name": "Ajay Kumar Yadav", "case_count": 3}
    fake = _base_fake(tracking=_tracking())
    fake.table("court_advocates").rows.append(existing_advocate)
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1", petitioner_advocates=["Ajay Kumar Yadav"]),
        causelist={},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    court_sync.sync_matter_court_data("m1", fake)

    advocates = fake.table("court_advocates").rows
    assert len(advocates) == 1  # never duplicated
    assert advocates[0]["case_count"] == 4

    links = fake.table("case_advocate_links").rows
    assert len(links) == 1
    assert links[0]["advocate_id"] == "adv-1"


def test_sync_creates_interlocutory_applications(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(
            cnr="CNR1",
            interlocutory_applications=[
                _FakeIAEntry(application_number="CRL.M.A. 12140/2026", filed_by="Deepak", filing_date="2026-04-18", status_raw="Pending"),
            ],
        ),
        causelist={},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    court_sync.sync_matter_court_data("m1", fake)

    ias = fake.table("interlocutory_applications").rows
    assert len(ias) == 1
    assert ias[0]["application_number"] == "CRL.M.A. 12140/2026"
    assert ias[0]["filed_by"] == "Deepak"
    assert ias[0]["current_status"] == "PENDING"


def test_sync_updates_existing_ia_no_duplicate(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(
            cnr="CNR1",
            interlocutory_applications=[
                _FakeIAEntry(application_number="IA/1/2026", filed_by="Deepak", filing_date="2026-04-18", status_raw="Pending"),
            ],
        ),
        causelist={},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)
    court_sync.sync_matter_court_data("m1", fake)

    gateway2 = _FakeGateway(
        case_detail=_FakeCaseDetail(
            cnr="CNR1",
            interlocutory_applications=[
                _FakeIAEntry(application_number="IA/1/2026", filed_by="Deepak", filing_date="2026-04-18", status_raw="Allowed"),
            ],
        ),
        causelist={},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway2)
    court_sync.sync_matter_court_data("m1", fake)

    ias = fake.table("interlocutory_applications").rows
    assert len(ias) == 1
    assert ias[0]["current_status"] == "GRANTED"


def test_unrecognized_ia_status_defaults_to_pending(monkeypatch):
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(
            cnr="CNR1",
            interlocutory_applications=[
                _FakeIAEntry(application_number="IA/2/2026", filed_by="Deepak", filing_date="2026-04-18", status_raw="Some Unseen Status"),
            ],
        ),
        causelist={},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)
    court_sync.sync_matter_court_data("m1", fake)
    assert fake.table("interlocutory_applications").rows[0]["current_status"] == "PENDING"


def test_advocate_persistence_failure_does_not_break_sync(monkeypatch):
    """A failure writing advocates/IAs must not discard the case_lookup
    result or block the rest of sync -- same partial-success posture as a
    causelist_batch failure."""
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(
        case_detail=_FakeCaseDetail(cnr="CNR1", petitioner_advocates=["Someone"]),
        causelist={"CNR1": _FakeCauselistEntry(cnr="CNR1", has_causelist=True)},
    )
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)
    monkeypatch.setattr(
        court_sync,
        "_upsert_case_advocates",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = court_sync.sync_matter_court_data("m1", fake)
    assert result["status"] == "synced"
    tracking_row = fake.table("court_case_tracking").rows[0]
    assert tracking_row["sync_status"] == "synced"


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


def test_cnr_not_found_sets_distinct_last_error(monkeypatch):
    """Found in production (2026-09-07): a 404 (bad/nonexistent CNR) was
    getting the same generic 'Case lookup failed' last_error as a real
    provider outage, which the router then turned into a misleading
    'unable to reach the provider' message for a plain CNR typo."""
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(case_lookup_raises=CourtDataNotFoundError("eCourts API returned 404 (request_id=abc)"))
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    with pytest.raises(CourtDataNotFoundError):
        court_sync.sync_matter_court_data("m1", fake)

    tracking_row = fake.table("court_case_tracking").rows[0]
    assert tracking_row["sync_status"] == "error"
    assert tracking_row["last_error"] == "CNR not found on eCourts. Double-check the CNR and try again."


def test_quota_exceeded_sets_distinct_last_error(monkeypatch):
    """Found in production (2026-09-07): a 402 (quota/billing) was getting
    the same generic 'Case lookup failed' last_error as a real outage --
    same conflation as the 404 case above, different root cause."""
    fake = _base_fake(tracking=_tracking())
    gateway = _FakeGateway(case_lookup_raises=CourtDataQuotaExceededError("eCourts API returned 402 (request_id=abc)"))
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    with pytest.raises(CourtDataQuotaExceededError):
        court_sync.sync_matter_court_data("m1", fake)

    tracking_row = fake.table("court_case_tracking").rows[0]
    assert tracking_row["sync_status"] == "error"
    assert "quota/billing" in tracking_row["last_error"]


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


def test_sync_persists_ecourts_orders_and_files(monkeypatch):
    """Verifies that interim orders from eCourts JSON are saved into the `orders` table
    and `court_case_tracking` table."""
    fake = _base_fake(tracking=_tracking())
    case_detail = _FakeCaseDetail(
        cnr="CNR1",
        court_name="Delhi High Court",
        interim_orders=[
            {
                "order_date": "2026-04-20",
                "description": "View ORDER",
                "order_url": "order-1.pdf",
            }
        ],
        filed_documents=[{"doc_id": "doc123", "name": "Bail Application"}],
    )
    gateway = _FakeGateway(case_detail=case_detail, causelist={})
    monkeypatch.setattr(court_sync, "CourtDataGateway", lambda: gateway)

    result = court_sync.sync_matter_court_data("m1", fake)
    assert result["status"] == "synced"

    # Orders table check
    order_rows = fake.table("orders").rows
    assert len(order_rows) == 1
    assert order_rows[0]["order_date"] == "2026-04-20"
    assert order_rows[0]["file_url"] == "order-1.pdf"
    assert order_rows[0]["source"] == "ecourts"
    assert order_rows[0]["court"] == "Delhi High Court"

    # Tracking table check
    tracking_row = fake.table("court_case_tracking").rows[0]
    assert len(tracking_row.get("interim_orders", [])) == 1
    assert tracking_row["interim_orders"][0]["order_url"] == "order-1.pdf"

