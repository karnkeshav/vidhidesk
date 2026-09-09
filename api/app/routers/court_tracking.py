"""CNR / court-tracking endpoints (Litigation Intelligence + eCourts,
27 Aug 2026). The CNR belongs to the existing Matter -- this router never
creates a second "Court Case" object; court_case_tracking is a tracking-
state row referencing matter_id, matching the same rule Section 4 of the
spec states explicitly.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import CurrentUser, get_current_user
from app.db import service_client
from app.models.schemas import (
    CaseAdvocateOut,
    CauselistEntryOut,
    CourtCasePreviewOut,
    CourtCaseSearchResultOut,
    CourtCaseTrackingOut,
    CourtCaseTrackingUpdate,
    InterlocutoryApplicationOut,
)
from app.services import court_sync, court_tracking
from app.services.court_data_gateway import (
    CourtDataGateway,
    CourtDataGatewayError,
    CourtDataNotConfiguredError,
    CourtDataNotFoundError,
    CourtDataQuotaExceededError,
)

router = APIRouter(prefix="/api", tags=["court-tracking"])


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    return resp.data[0]


@router.get("/matters/{matter_id}/court-tracking", response_model=CourtCaseTrackingOut)
def get_court_tracking(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """Returns the matter's tracking state, creating an empty (disabled,
    no CNR) row on first access -- "not yet set up" is a normal UI state,
    not a 404."""
    matter = _get_matter_or_404(user, matter_id)
    return court_tracking.get_or_create_tracking(matter_id, matter["organization_id"], user.db)


@router.patch("/matters/{matter_id}/court-tracking", response_model=CourtCaseTrackingOut)
def update_court_tracking(
    matter_id: str,
    payload: CourtCaseTrackingUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Set/edit the CNR and enable/disable tracking. Does not itself call
    the provider -- see POST .../court-tracking/sync for that."""
    matter = _get_matter_or_404(user, matter_id)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")
    return court_tracking.update_tracking(matter_id, matter["organization_id"], update_data, user.db)


@router.post("/matters/{matter_id}/court-tracking/sync", response_model=CourtCaseTrackingOut)
def trigger_court_sync(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """Manually trigger an eCourts sync now, outside the scheduled window.
    Ownership is verified via user.db/RLS BEFORE reaching for
    service_client() -- court_sync.sync_matter_court_data() needs
    service-role privileges (writes court_sync_log, which has no
    authenticated-role policy at all) and would happily act on any
    matter_id it's given, so this router's own ownership check is what
    actually enforces tenant isolation for this one endpoint, not RLS."""
    _get_matter_or_404(user, matter_id)
    sc = service_client()
    try:
        court_sync.sync_matter_court_data(matter_id, sc)
    except court_sync.CourtSyncSkipped as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CourtDataNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="eCourts integration is not configured on this server.",
        ) from exc
    except CourtDataNotFoundError as exc:
        # Distinct from the generic 502 below: a 404 means eCourts doesn't
        # recognize this CNR at all (typo, wrong court code, or genuinely
        # not on record) -- a client-error 400, not a server/connectivity
        # problem. Conflating the two sent a real user (2026-09-07)
        # chasing a nonexistent outage over a CNR typo. last_error on the
        # tracking row already carries the same message (set by
        # sync_matter_court_data).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CNR not found on eCourts. Double-check the CNR and try again.",
        ) from exc
    except CourtDataQuotaExceededError as exc:
        # Distinct from the generic 502 below for the same reason as 404
        # above: 402 means the eCourts account's own quota/billing needs
        # attention, not a connectivity/outage problem -- found the same
        # day (2026-09-07) as the 404 case, right after a burst of testing
        # calls exhausted the account's quota. 402 (not 502/503) mirrors
        # the provider's own status code, since this genuinely is a
        # payment-required condition, not a transient server failure.
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="eCourts API quota/billing issue. Check the eCourts account's plan/billing status.",
        ) from exc
    except CourtDataGatewayError:
        # Never echo the raw provider error to the client -- last_error on
        # the tracking row (set by sync_matter_court_data before this
        # raises) already carries a safe summary; the GET endpoint surfaces it.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach the eCourts provider right now. See last_error for detail; try again shortly.",
        )
    rows = sc.table("court_case_tracking").select("*").eq("matter_id", matter_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracking record not found")
    return rows[0]


@router.get("/matters/{matter_id}/causelist", response_model=list[CauselistEntryOut])
def list_causelist(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """The cached causelist entries court_sync.py has written for this
    matter, most recent hearing_date first. RLS (case_advocate_links_org_
    member_all's sibling, causelist_org_member_all) already scopes this to
    the caller's own organization; the matter-ownership check below just
    turns "not yours" into a clean 404 instead of an empty list that looks
    identical to "no causelist yet"."""
    _get_matter_or_404(user, matter_id)
    resp = (
        user.db.table("court_hearings_causelist")
        .select("*")
        .eq("matter_id", matter_id)
        .order("hearing_date", desc=True)
        .execute()
    )
    return resp.data


@router.get("/matters/{matter_id}/interlocutory-applications", response_model=list[InterlocutoryApplicationOut])
def list_interlocutory_applications(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """Populated by app/services/court_sync.py on each successful sync
    (see InterlocutoryApplicationOut's docstring) -- empty only when the
    matter hasn't synced yet or genuinely has no IAs on record."""
    _get_matter_or_404(user, matter_id)
    resp = (
        user.db.table("interlocutory_applications")
        .select("*")
        .eq("matter_id", matter_id)
        .order("filing_date", desc=True)
        .execute()
    )
    return resp.data


@router.get("/matters/{matter_id}/case-advocates", response_model=list[CaseAdvocateOut])
def list_case_advocates(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """Populated by app/services/court_sync.py on each successful sync
    (see CaseAdvocateOut's docstring) -- empty only when the matter hasn't
    synced yet or genuinely has no advocates on record. court_advocates
    has no organization_id (it's a shared cross-org directory, see
    0026/0027's migration notes), so the join and the tenant-ownership
    check both happen here rather than relying on RLS on court_advocates
    alone."""
    matter = _get_matter_or_404(user, matter_id)
    links_resp = (
        user.db.table("case_advocate_links")
        .select("*")
        .eq("matter_id", matter_id)
        .execute()
    )
    links = links_resp.data or []
    if not links:
        return []
    advocate_ids = [link["advocate_id"] for link in links]
    advocates_resp = user.db.table("court_advocates").select("*").in_("id", advocate_ids).execute()
    advocates_by_id = {a["id"]: a for a in (advocates_resp.data or [])}
    return [
        {
            "advocate_id": link["advocate_id"],
            "name": advocates_by_id.get(link["advocate_id"], {}).get("name", "Unknown"),
            "bar_council_id": advocates_by_id.get(link["advocate_id"], {}).get("bar_council_id"),
            "phone": advocates_by_id.get(link["advocate_id"], {}).get("phone"),
            "email": advocates_by_id.get(link["advocate_id"], {}).get("email"),
            "office_address": advocates_by_id.get(link["advocate_id"], {}).get("office_address"),
            "role": link["role"],
            "first_appeared": link.get("first_appeared"),
            "last_appeared": link.get("last_appeared"),
        }
        for link in links
        if link["advocate_id"] in advocates_by_id
    ]


def _cached_preview_from_tracking(user: CurrentUser, cnr: str) -> dict | None:
    """Cache-first (added 2026-09-07, real user request after seeing every
    Search click burn live eCourts quota with zero caching): reuse a
    prior successful sync's already-verified typed fields for this exact
    CNR instead of calling the live API again. Queried via user.db, so
    RLS on court_case_tracking already scopes this to the caller's own
    organization -- no cross-tenant data exposure. Only a row where
    provider_metadata is actually populated counts as "cached" -- an
    idle/never-synced/errored tracking row (provider_metadata null) is
    not a cache hit and falls through to the live call. Reads only,
    matching this endpoint's existing "persists nothing" posture."""
    rows = (
        user.db.table("court_case_tracking")
        .select("cnr_number,court_name,judge,case_status,petitioners,respondents,provider_metadata,last_synced_at")
        .eq("cnr_number", cnr)
        .execute()
        .data
        or []
    )
    candidates = [r for r in rows if r.get("provider_metadata")]
    if not candidates:
        return None
    # More than one of the caller's own matters could share a CNR (rare,
    # but not disallowed) -- the most recently synced one wins.
    candidates.sort(key=lambda r: r.get("last_synced_at") or "", reverse=True)
    row = candidates[0]
    pm = row.get("provider_metadata") or {}
    case_data = (pm.get("data") or {}).get("courtCaseData") or {}
    interim_orders = []
    for o in case_data.get("interimOrders") or []:
        if isinstance(o, dict):
            interim_orders.append(
                {
                    "order_date": o.get("orderDate"),
                    "description": o.get("description"),
                    "order_url": o.get("orderUrl"),
                }
            )
    filed_docs = [d for d in case_data.get("filedDocuments") or [] if isinstance(d, dict)]

    return {
        "cnr": row["cnr_number"],
        "court_name": row.get("court_name"),
        "judge": row.get("judge"),
        "status": row.get("case_status"),
        "petitioners": row.get("petitioners") or [],
        "respondents": row.get("respondents") or [],
        "interim_orders": row.get("interim_orders") or interim_orders,
        "filed_documents": row.get("filed_documents") or filed_docs,
    }


@router.get("/court-lookup-preview", response_model=CourtCasePreviewOut)
def preview_court_case(cnr: str, user: CurrentUser = Depends(get_current_user)):
    """Looks up a single CNR the caller already has, to confirm it's the
    right case BEFORE it's saved to a matter -- not matter-scoped, and
    persists nothing (same posture as GET /court-search below, just for a
    known CNR instead of a broad search). The caller still PATCHes
    .../court-tracking with the confirmed CNR to actually save it; that
    PATCH is what triggers the real sync and is the only thing that
    writes to court_case_tracking.

    Checks for a cached result (_cached_preview_from_tracking) before
    ever reaching for the live provider -- see that function's comment."""
    if not cnr.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide a CNR")
    normalized_cnr = cnr.strip().upper()

    cached = _cached_preview_from_tracking(user, normalized_cnr)
    if cached:
        return cached

    try:
        gateway = CourtDataGateway()
        detail = gateway.case_lookup(normalized_cnr)
    except CourtDataNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="eCourts integration is not configured on this server.",
        ) from exc
    except CourtDataNotFoundError as exc:
        # Same reasoning as trigger_court_sync's own handling: a 404 means
        # eCourts doesn't recognize this CNR at all (typo, wrong court
        # code, or genuinely not on record) -- a client-error 400, not a
        # server/connectivity problem. Without this, CourtDataNotFoundError
        # (a CourtDataGatewayError subclass) fell through to the generic
        # 502 below on every search-step lookup, not just the save-step
        # sync -- found 2026-09-07 when a real bad-CNR search showed the
        # same "Could not find or reach" message trigger_court_sync had
        # already been fixed to stop giving.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CNR not found on eCourts. Double-check the CNR and try again.",
        ) from exc
    except CourtDataQuotaExceededError as exc:
        # Same reasoning as trigger_court_sync's own handling below.
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="eCourts API quota/billing issue. Check the eCourts account's plan/billing status.",
        ) from exc
    except CourtDataGatewayError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not find or reach that CNR on the eCourts provider. Double-check it and try again.",
        )
    return {
        "cnr": detail.cnr,
        "court_name": detail.court_name,
        "judge": detail.judge,
        "status": detail.status,
        "petitioners": detail.petitioners,
        "respondents": detail.respondents,
        "interim_orders": detail.interim_orders,
        "filed_documents": detail.filed_documents,
    }


@router.get("/court-search", response_model=CourtCaseSearchResultOut)
def search_court_cases(
    query: str | None = None,
    advocates: list[str] | None = Query(default=None),
    case_numbers: list[str] | None = Query(default=None),
    court_codes: list[str] | None = Query(default=None),
    case_types: list[str] | None = Query(default=None),
    page: int = 1,
    page_size: int = 20,
    user: CurrentUser = Depends(get_current_user),
):
    """Search eCourts by advocate name, case number, party name, or court
    to find a CNR when one isn't already known -- not matter-scoped, and
    persists nothing. The caller still PATCHes .../court-tracking with the
    chosen CNR to actually attach it to a matter. See
    CourtDataGateway.case_search() for this endpoint's verification
    caveat -- unlike CNR-based lookups, its exact field names have not
    been confirmed against a live provider response."""
    if not any([query, advocates, case_numbers, court_codes, case_types]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide at least one search filter")
    try:
        gateway = CourtDataGateway()
        result = gateway.case_search(
            query=query,
            advocates=advocates,
            case_numbers=case_numbers,
            court_codes=court_codes,
            case_types=case_types,
            page=page,
            page_size=page_size,
        )
    except CourtDataNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="eCourts integration is not configured on this server.",
        ) from exc
    except CourtDataNotFoundError as exc:
        # Same gap as preview_court_case had: case_search() shares
        # CourtDataGateway._request(), so a 404 from the provider (no
        # matches for these filters) is also a CourtDataGatewayError
        # subclass and would otherwise fall through to the generic 502
        # below -- a client-side "no results", not a server/connectivity
        # problem.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No matching cases found for these filters on eCourts.",
        ) from exc
    except CourtDataQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="eCourts API quota/billing issue. Check the eCourts account's plan/billing status.",
        ) from exc
    except CourtDataGatewayError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach the eCourts provider right now. Try again shortly.",
        )
    return {
        "items": [
            {
                "cnr": item.cnr,
                "case_number": item.case_number,
                "court_name": item.court_name,
                "case_type": item.case_type,
                "status": item.status,
                "petitioners": item.petitioners,
                "respondents": item.respondents,
                "advocates": item.advocates,
            }
            for item in result.items
        ],
        "total": result.total,
        "has_next_page": result.has_next_page,
    }
