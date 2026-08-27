"""Hearing / Argument Brief endpoints (Litigation Intelligence + eCourts,
27 Aug 2026). Lawyer review is mandatory -- see review_hearing_brief_endpoint,
the only endpoint that can move a brief past 'draft'; no code path in this
router or app/services/hearing_brief.py ever sets status to anything but
'draft' at generation time.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.models.schemas import HearingBriefOut, HearingBriefReviewRequest
from app.services import hearing_brief
from app.services.llm_gateway import ProviderError

router = APIRouter(prefix="/api", tags=["hearing-briefs"])


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    return resp.data[0]


@router.post(
    "/matters/{matter_id}/hearings/{hearing_id}/briefs",
    response_model=HearingBriefOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_hearing_brief_endpoint(
    matter_id: str,
    hearing_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Generate a new versioned Hearing Brief for this hearing, from the
    Matter Intelligence Bundle (app/services/matter_bundle.py) --
    organization/matter isolation is enforced by user.db/RLS throughout,
    same as every other AI-generation endpoint in this codebase."""
    _get_matter_or_404(user, matter_id)
    try:
        return hearing_brief.generate_hearing_brief(matter_id, hearing_id, user.db)
    except hearing_brief.HearingBriefError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"All LLM providers failed: {exc}") from exc


@router.get("/matters/{matter_id}/hearings/{hearing_id}/briefs", response_model=list[HearingBriefOut])
def list_hearing_briefs_endpoint(
    matter_id: str,
    hearing_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """List all Hearing Brief versions for this hearing, most recent first."""
    _get_matter_or_404(user, matter_id)
    return hearing_brief.list_hearing_briefs(hearing_id, user.db)


@router.patch("/matters/{matter_id}/briefs/{brief_id}/review", response_model=HearingBriefOut)
def review_hearing_brief_endpoint(
    matter_id: str,
    brief_id: str,
    payload: HearingBriefReviewRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Lawyer review workflow: draft -> reviewed -> approved_for_hearing.
    The ONLY way a brief's status ever changes -- generation always
    starts at 'draft' (spec Section 11)."""
    _get_matter_or_404(user, matter_id)
    try:
        return hearing_brief.review_hearing_brief(
            brief_id, status=payload.status, lawyer_edits=payload.lawyer_edits, db=user.db
        )
    except hearing_brief.HearingBriefError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
