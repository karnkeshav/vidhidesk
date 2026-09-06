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
from app.models.schemas import CourtCasePreviewOut, CourtCaseSearchResultOut, CourtCaseTrackingOut, CourtCaseTrackingUpdate
from app.services import court_sync, court_tracking
from app.services.court_data_gateway import CourtDataGateway, CourtDataGatewayError, CourtDataNotConfiguredError

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


@router.get("/court-lookup-preview", response_model=CourtCasePreviewOut)
def preview_court_case(cnr: str, user: CurrentUser = Depends(get_current_user)):
    """Looks up a single CNR the caller already has, to confirm it's the
    right case BEFORE it's saved to a matter -- not matter-scoped, and
    persists nothing (same posture as GET /court-search below, just for a
    known CNR instead of a broad search). The caller still PATCHes
    .../court-tracking with the confirmed CNR to actually save it; that
    PATCH is what triggers the real sync and is the only thing that
    writes to court_case_tracking."""
    if not cnr.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide a CNR")
    try:
        gateway = CourtDataGateway()
        detail = gateway.case_lookup(cnr.strip())
    except CourtDataNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="eCourts integration is not configured on this server.",
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
