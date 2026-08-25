from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends

from app.auth import CurrentUser, get_current_user
from app.models.schemas import HearingCreate, HearingOut, HearingUpdate

router = APIRouter(prefix="/api/hearings", tags=["hearings"])


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
    row = {**body.model_dump(), "user_id": user.id}
    resp = user.db.table("hearings").insert(row).execute()
    return resp.data[0]


@router.get("", response_model=list[HearingOut])
def list_hearings(user: CurrentUser = Depends(get_current_user)):
    resp = user.db.table("hearings").select("*").order("hearing_at").execute()
    return resp.data


@router.patch("/{hearing_id}", response_model=HearingOut)
def update_hearing(
    hearing_id: str, body: HearingUpdate, user: CurrentUser = Depends(get_current_user)
):
    _get_hearing_or_404(user, hearing_id)
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return _get_hearing_or_404(user, hearing_id)
    resp = user.db.table("hearings").update(update_data).eq("id", hearing_id).execute()
    return resp.data[0]


@router.delete("/{hearing_id}")
def delete_hearing(hearing_id: str, user: CurrentUser = Depends(get_current_user)):
    _get_hearing_or_404(user, hearing_id)
    user.db.table("hearings").delete().eq("id", hearing_id).execute()
    return {"status": "deleted", "id": hearing_id}
