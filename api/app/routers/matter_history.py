"""Matter History endpoint (Hearing Intelligence, Iter 3B, 30 Aug 2026) --
a read-only chronological projection of a matter's own record (parties,
chronology, prior hearings, lawyer notes) for the Matter History tab at
/hearings/[hearingId]. Reuses app/services/matter_bundle.py's existing
assembly logic verbatim (the same function hearing_brief.py grounds its
LLM prompt with) instead of re-deriving chronology or exclusion rules
here or in the frontend -- this endpoint only projects a subset of that
bundle's fields relevant to history. No mutation capability, no LLM call,
no new table.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.models.schemas import MatterHistoryChronologyEntry, MatterHistoryOut
from app.services.matter_bundle import MatterBundleError, assemble_matter_bundle

router = APIRouter(prefix="/api", tags=["matter-history"])


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    return resp.data[0]


@router.get(
    "/matters/{matter_id}/hearings/{hearing_id}/history",
    response_model=MatterHistoryOut,
)
def get_matter_history(
    matter_id: str,
    hearing_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Prior hearings (excluding hearing_id itself), chronology, parties,
    and lawyer notes carried on those prior hearings -- everything the
    Matter History tab needs and nothing else (orders/pleadings/research
    belong to Legal Record / AI Intelligence, not here). user.db is
    RLS-scoped, same as every other endpoint in this codebase --
    organization isolation is enforced by Postgres, not by any check
    here."""
    _get_matter_or_404(user, matter_id)
    try:
        bundle = assemble_matter_bundle(matter_id, user.db, exclude_hearing_id=hearing_id)
    except MatterBundleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    missing: list[str] = []
    if not bundle.parties:
        missing.append("No parties recorded for this matter.")
    if not bundle.chronology:
        missing.append("No facts/chronology recorded for this matter.")
    if not bundle.hearings:
        missing.append("No prior hearing history recorded for this matter.")

    return MatterHistoryOut(
        matter_id=matter_id,
        parties=bundle.parties,
        chronology=[MatterHistoryChronologyEntry(**c) for c in bundle.chronology],
        prior_hearings=bundle.hearings,
        lawyer_notes=bundle.lawyer_notes,
        missing=missing,
    )
