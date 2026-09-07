"""Court sync orchestration (Litigation Intelligence + eCourts, 27 Aug
2026). Wires app/services/court_data_gateway.py's provider calls into
court_case_tracking / hearings / court_sync_log. Runs with
service_client() (bypasses RLS) since it is invoked from
scripts/court_sync_scheduler.py (no authenticated request context, see
that script's own docstring) -- every write below sets organization_id/
matter_id explicitly rather than relying on RLS to scope it, and the
organization access check below is this module's OWN enforcement of
tenant isolation and the "expired orgs don't consume eCourts usage"
policy, not a substitute for RLS on the authenticated read paths (which
still apply normally to every other router).

Strict matching (spec Section 7): every sync is keyed by CNR via
court_case_tracking.matter_id -> cnr_number -- never by party name.
Manual override protection: a hearing whose source='manual_override' is
never touched by sync -- checked before every write, not just documented.
Idempotency: hearings are upserted by (matter_id, hearing date), never
blindly inserted -- a repeat sync on the same day updates the same row.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.court_data_gateway import (
    CourtDataGateway,
    CourtDataGatewayError,
    CourtDataNotConfiguredError,
)
from app.services.notifications import notify_hearing_listed

logger = logging.getLogger("vidhidesk.court_sync")

_PAUSED_STATUSES = frozenset({"suspended", "expired"})


class CourtSyncSkipped(Exception):
    """Not an error -- tracking disabled, no CNR, or org access paused.
    Distinguished from a real provider/sync failure so the caller (the
    scheduler script) can log/count these differently from actual errors."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(sc, *, organization_id: str, matter_id: str, cnr: str | None, operation: str, status: str, request_id: str | None = None, error_message: str | None = None) -> None:
    try:
        sc.table("court_sync_log").insert(
            {
                "organization_id": organization_id,
                "matter_id": matter_id,
                "cnr_number": cnr,
                "operation": operation,
                "status": status,
                "provider_request_id": request_id,
                "error_message": error_message,
            }
        ).execute()
    except Exception:
        logger.warning("court_sync: failed to write court_sync_log for matter_id=%s", matter_id, exc_info=True)


def _upsert_hearing_from_causelist(sc, *, matter: dict[str, Any], entry) -> tuple[dict[str, Any] | None, bool]:
    """Returns (hearing_row, was_created). Returns (None, False) if the
    only matching hearing is protected by manual_override -- the caller
    must not treat that as a failure, just as "left alone on purpose"."""
    if not entry.date:
        return None, False

    existing = sc.table("hearings").select("*").eq("matter_id", matter["id"]).execute().data or []
    match = next((h for h in existing if str(h.get("hearing_at", "")).startswith(entry.date)), None)

    if match and match.get("source") == "manual_override":
        logger.info("court_sync: hearing %s is manual_override, sync skipped for this hearing", match["id"])
        return None, False

    payload = {
        "matter_id": matter["id"],
        "organization_id": matter["organization_id"],
        "court": entry.court,
        "bench": entry.bench,
        "item_no": entry.court_no,
        "listing_details": entry.raw,
        "source": "ecourts",
        "source_synced_at": _now_iso(),
    }

    if match:
        updated = sc.table("hearings").update(payload).eq("id", match["id"]).execute().data
        return (updated[0] if updated else None), False

    payload.update(
        {
            "user_id": matter["user_id"],
            "hearing_at": f"{entry.date}T00:00:00+00:00",
            "title": f"Hearing — {matter.get('title', 'Matter')}",
            "case_no": matter.get("case_number_formatted"),
        }
    )
    inserted = sc.table("hearings").insert(payload).execute().data
    return (inserted[0] if inserted else None), True


def _upsert_causelist_row(sc, *, matter: dict[str, Any], cnr: str, entry, judges: list[str]) -> None:
    """Upserts one row into court_hearings_causelist, keyed by the table's
    own (matter_id, hearing_date) unique constraint. Deliberately writes
    ONLY fields CourtDataGateway has already verified against a real
    provider response: court/bench/list_type/date come from CauselistEntry
    (verified 2026-08-28), judges comes from this same sync's case_lookup
    call (verified 2026-09-06, see CourtDataGateway.case_lookup). It never
    writes court_advocates/case_advocate_links/interlocutory_applications
    -- those tables' provider field shapes are unverified (see
    scripts/ecourts_spike.py); guessing them was the cause of the earlier
    case_lookup envelope bug and is not repeated here."""
    if not entry.date:
        return

    existing = (
        sc.table("court_hearings_causelist")
        .select("*")
        .eq("matter_id", matter["id"])
        .eq("hearing_date", entry.date)
        .execute()
        .data
        or []
    )

    payload = {
        "organization_id": matter["organization_id"],
        "matter_id": matter["id"],
        "cnr_number": cnr,
        "hearing_date": entry.date,
        "bench_number": entry.bench,
        "judge_names": judges or None,
        "court_location": entry.court,
        "causelist_type": entry.list_type,
        "fetched_at": _now_iso(),
    }

    if existing:
        sc.table("court_hearings_causelist").update(payload).eq("id", existing[0]["id"]).execute()
    else:
        sc.table("court_hearings_causelist").insert(payload).execute()


def sync_matter_court_data(matter_id: str, sc) -> dict[str, Any]:
    """Full sync for one matter. `sc` is a service_client() instance --
    the caller (scheduler script) is responsible for supplying it; this
    function never constructs its own, to keep it testable against a
    fake."""
    tracking_rows = (
        sc.table("court_case_tracking").select("*").eq("matter_id", matter_id).limit(1).execute().data
    )
    if not tracking_rows or not tracking_rows[0].get("tracking_enabled"):
        raise CourtSyncSkipped("tracking not enabled for this matter")
    tracking = tracking_rows[0]

    cnr = tracking.get("cnr_number")
    if not cnr:
        raise CourtSyncSkipped("no CNR set for this matter")

    matter_rows = sc.table("matters").select("*").eq("id", matter_id).limit(1).execute().data
    if not matter_rows:
        raise CourtSyncSkipped(f"matter {matter_id} not found")
    matter = matter_rows[0]
    organization_id = matter["organization_id"]

    org_rows = sc.table("organizations").select("access_enabled,subscription_status").eq("id", organization_id).limit(1).execute().data
    if not org_rows or not org_rows[0]["access_enabled"] or org_rows[0]["subscription_status"] in _PAUSED_STATUSES:
        # Policy (spec Section 8): expired/suspended orgs do not consume
        # eCourts API usage. Cached historical data (tracking row, past
        # hearings) is left exactly as-is -- only the outbound call is skipped.
        raise CourtSyncSkipped(f"organization {organization_id} access is not active")

    sc.table("court_case_tracking").update({"sync_status": "syncing"}).eq("id", tracking["id"]).execute()

    gateway = CourtDataGateway()
    try:
        case_detail = gateway.case_lookup(cnr)
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="case_lookup", status="success")
    except CourtDataNotConfiguredError:
        raise
    except CourtDataGatewayError as exc:
        # provider_metadata is explicitly cleared here, not left as-is: a
        # matter whose CNR changes and then fails to look up would
        # otherwise keep serving the PREVIOUS (different) case's cached
        # data under the new CNR -- found by testing two real CNRs against
        # the same matter, where the second (failed) lookup left the first
        # case's petitioner/court/FIR data sitting there mislabeled under
        # the new, never-successfully-looked-up CNR.
        sc.table("court_case_tracking").update(
            {
                "sync_status": "error",
                "last_error": "Case lookup failed. See sync log for detail.",
                "last_synced_at": _now_iso(),
                "provider_metadata": None,
            }
        ).eq("id", tracking["id"]).execute()
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="case_lookup", status="error", error_message=str(exc))
        raise

    hearing_created = False
    hearing_row: dict[str, Any] | None = None
    # 'nextListing'.date, straight from causelist_batch (see
    # CourtDataGateway.causelist_batch) -- exactly what this column means.
    # Was never actually written before this fix, despite existing since
    # 0025 (court_case_tracking.next_hearing_date), found while wiring up
    # the case-details UI.
    next_hearing_date: str | None = None
    try:
        causelist = gateway.causelist_batch([cnr])
        entry = causelist.get(cnr)
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="causelist_batch", status="success")
        if entry and entry.has_causelist:
            hearing_row, hearing_created = _upsert_hearing_from_causelist(sc, matter=matter, entry=entry)
            _upsert_causelist_row(sc, matter=matter, cnr=cnr, entry=entry, judges=case_detail.judges)
            next_hearing_date = entry.date
    except CourtDataGatewayError as exc:
        # A causelist failure does not invalidate the case_lookup we
        # already have -- log it, keep going, surface a partial success.
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="causelist_batch", status="error", error_message=str(exc))

    sc.table("court_case_tracking").update(
        {
            "sync_status": "synced",
            "last_error": None,
            "last_synced_at": _now_iso(),
            "provider_metadata": case_detail.raw,
            # Same already-verified fields case_detail carries -- stored
            # separately so a caller (case-details UI) never has to parse
            # provider_metadata's raw envelope itself, see 0028's migration
            # note.
            "court_name": case_detail.court_name,
            "judge": case_detail.judge,
            "case_status": case_detail.status,
            "petitioners": case_detail.petitioners,
            "respondents": case_detail.respondents,
            "next_hearing_date": next_hearing_date,
        }
    ).eq("id", tracking["id"]).execute()

    if hearing_row:
        notify_hearing_listed(
            sc,
            organization_id=organization_id,
            user_id=matter["user_id"],
            matter_id=matter_id,
            matter_title=matter.get("title", "Matter"),
            hearing_date=str(hearing_row.get("hearing_at", ""))[:10],
            court=hearing_row.get("court"),
            bench=hearing_row.get("bench"),
            item_no=hearing_row.get("item_no"),
        )

    return {
        "status": "synced",
        "matter_id": matter_id,
        "hearing_id": hearing_row["id"] if hearing_row else None,
        "hearing_created": hearing_created,
    }


def matters_due_for_sync(sc) -> list[dict[str, Any]]:
    """Every tracking-enabled matter -- the scheduler script itself
    decides the lookahead window (spec Section 8: "configurable sync
    window/interval/lookahead") by filtering on next_hearing_date after
    calling this; kept here as a plain, un-filtered list so that decision
    stays in one place (the script), not duplicated into this module."""
    return sc.table("court_case_tracking").select("*").eq("tracking_enabled", True).execute().data or []
