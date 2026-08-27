from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query

from app.auth import CurrentUser, get_current_user
from app.models.schemas import HearingCreate, HearingOut, HearingUpdate

router = APIRouter(prefix="/api/hearings", tags=["hearings"])


def _require_organization(user: CurrentUser) -> str:
    # Same rationale as matters.py::create_matter -- see that comment.
    if not user.organization_id:
        raise HTTPException(
            status_code=400,
            detail="No organization found for this account. Please sign out and sign in again.",
        )
    return user.organization_id


def _get_hearing_or_404(user: CurrentUser, hearing_id: str) -> dict:
    resp = user.db.table("hearings").select("*").eq("id", hearing_id).limit(1).execute()
    if not resp.data:
        # RLS makes another user's hearing look identical to a missing one —
        # that's the point: no ownership-probing oracle. Same pattern as
        # matters.py::_get_matter_or_404.
        raise HTTPException(status_code=404, detail="Hearing not found")
    return resp.data[0]


@router.post("", response_model=HearingOut, status_code=201)
def create_hearing(body: HearingCreate, user: CurrentUser = Depends(get_current_user)):
    organization_id = _require_organization(user)
    row = {**body.model_dump(), "user_id": user.id, "organization_id": organization_id}
    resp = user.db.table("hearings").insert(row).execute()
    return resp.data[0]


@router.get("", response_model=list[HearingOut])
def list_hearings(
    matter_id: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    """matter_id, when given, scopes to that matter's own tracked hearings
    -- reuses this same table/endpoint rather than adding a parallel
    matter-scoped hearings route (litigation.py's /matters/{id}/hearings
    already exists for the separate litigation_hearings docket table;
    this is intentionally the OTHER hearing concept -- see
    0025_litigation_intelligence_ecourts.sql's header note)."""
    query = user.db.table("hearings").select("*")
    if matter_id:
        query = query.eq("matter_id", matter_id)
    resp = query.order("hearing_at").execute()
    return resp.data


@router.patch("/{hearing_id}", response_model=HearingOut)
def update_hearing(
    hearing_id: str, body: HearingUpdate, user: CurrentUser = Depends(get_current_user)
):
    _get_hearing_or_404(user, hearing_id)
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return _get_hearing_or_404(user, hearing_id)
    # A human editing court/bench/item_no through this endpoint is the
    # "lawyer override" case (spec Section 7): mark it so a later eCourts
    # sync (app/services/court_sync.py::_upsert_hearing_from_causelist)
    # skips this hearing instead of silently clobbering the correction.
    if any(f in update_data for f in ("court", "bench", "item_no")):
        update_data["source"] = "manual_override"
    resp = user.db.table("hearings").update(update_data).eq("id", hearing_id).execute()
    return resp.data[0]


@router.delete("/{hearing_id}")
def delete_hearing(hearing_id: str, user: CurrentUser = Depends(get_current_user)):
    _get_hearing_or_404(user, hearing_id)
    user.db.table("hearings").delete().eq("id", hearing_id).execute()
    return {"status": "deleted", "id": hearing_id}
