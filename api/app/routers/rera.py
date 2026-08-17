from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import CurrentUser, get_current_user
from app.models.schemas import (
    RERA_PHASE1_STATES,
    RERAWalkthroughProcedureOut,
    RERAWalkthroughProgressOut,
    RERAWalkthroughProgressUpdate,
    RERAWalkthroughStepOut,
)
from app.services import rera

router = APIRouter(prefix="/api/rera", tags=["rera"])


@router.get("/states", response_model=list[str])
def list_states(_user: CurrentUser = Depends(get_current_user)):
    """Phase 1 supported states for RERA filing walkthroughs (ADR-010).
    Static and deterministic — not derived from curated content, since an
    empty rera_guides table must not be indistinguishable from
    "this state genuinely isn't supported yet"."""
    return list(RERA_PHASE1_STATES)


@router.get("/procedures", response_model=list[RERAWalkthroughProcedureOut])
def list_procedures(
    state: str = Query(..., min_length=1),
    user: CurrentUser = Depends(get_current_user),
):
    """Procedures actually curated for a state, derived from real
    rera_guides rows. An unsupported/uncurated state returns an empty
    list, not a fabricated one — see rera.py::list_procedures."""
    try:
        return rera.list_procedures(state, user.db)
    except rera.RERAError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/walkthrough/{state}/{procedure}", response_model=list[RERAWalkthroughStepOut])
def get_walkthrough_steps(
    state: str,
    procedure: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Ordered steps for one state+procedure. Empty list (not a 404) when
    the state is supported but nothing has been curated for this
    procedure yet — an advocate should see "nothing here yet", never a
    fabricated step."""
    try:
        return rera.list_walkthrough_steps(state, procedure, user.db)
    except rera.RERAError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/walkthrough/{state}/{procedure}/progress", response_model=RERAWalkthroughProgressOut | None)
def get_walkthrough_progress(
    state: str,
    procedure: str,
    matter_id: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    """Caller's own progress only — user.db is RLS-scoped
    (rera_walkthrough_progress_owner_all, migration 0019), so this can
    never return another user's row regardless of query parameters."""
    try:
        return rera.get_progress(user.id, state, procedure, matter_id, user.db)
    except rera.RERAError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/walkthrough/{state}/{procedure}/progress", response_model=RERAWalkthroughProgressOut)
def update_walkthrough_progress(
    state: str,
    procedure: str,
    payload: RERAWalkthroughProgressUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Create-or-update the caller's own progress. `payload.matter_id`, if
    given, is independently re-validated here (ownership via user.db RLS +
    module='rera' check, app/services/rera.py::_validate_rera_matter) —
    never trusted from the request body alone, so a non-RERA or
    not-owned matter_id fails closed with 400, not silently accepted."""
    try:
        return rera.upsert_progress(
            user.id,
            state,
            procedure,
            payload.matter_id,
            payload.current_step_no,
            payload.mark_step_complete_id,
            payload.mark_step_incomplete_id,
            user.db,
        )
    except rera.RERAError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
