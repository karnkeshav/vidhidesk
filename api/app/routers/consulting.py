"""Consulting & Legal Research (Phase 1 backend) router.

Two endpoints, matching the documented product workflow (Product_Vision.md
Module 4, Build_Tracker.md Sprint 4): a legal question either starts a new
Consulting matter or continues an existing one as a follow-up (new
analysis version, never a new matter).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.models.schemas import ConsultingAnalysisOut, ConsultingAnalyzeRequest, MatterCreate
from app.routers.matters import create_matter
from app.services import consulting
from app.services.llm_gateway import ProviderError

router = APIRouter(prefix="/api/consulting", tags=["consulting"])

# How much of a new question to use as the auto-created matter's title —
# MatterCreate.title caps at 200 chars; kept well short of that for a
# readable matter list, same idea as Contracts' auto-generated titles.
_TITLE_MAX_LEN = 80


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        # RLS makes another user's matter look identical to a missing one —
        # same no-ownership-probing-oracle convention as every other
        # router in this codebase.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    return resp.data[0]


def _derive_title(question: str) -> str:
    q = question.strip()
    return q if len(q) <= _TITLE_MAX_LEN else q[: _TITLE_MAX_LEN - 1].rstrip() + "…"


@router.post("/analyze", response_model=ConsultingAnalysisOut, status_code=status.HTTP_201_CREATED)
def analyze(payload: ConsultingAnalyzeRequest, user: CurrentUser = Depends(get_current_user)):
    """Submit a legal question. Omitting `matter_id` creates a new
    Consulting matter (module='consulting', via the existing generic
    matters.create_matter — no duplicate matter-creation logic); supplying
    an existing matter_id is a follow-up: a new analysis version inside
    the SAME matter, per the product's explicit "never a new matter per
    follow-up" requirement.

    Combines: request validation (ConsultingAnalyzeRequest — rejects
    empty/whitespace-only/too-short questions), PII masking, RAG
    statutory retrieval, the LLM Gateway (task_type='consulting_analyst'),
    and the Citation Verifier — see app/services/consulting.py for the
    deterministic-vs-LLM trust boundary this endpoint enforces."""
    if payload.matter_id:
        matter = _get_matter_or_404(user, payload.matter_id)
        if matter.get("module") != "consulting":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="matter_id does not refer to a Consulting matter",
            )
        matter_id = matter["id"]
    else:
        created = create_matter(
            MatterCreate(title=_derive_title(payload.question), module="consulting"),
            user,
        )
        matter_id = created["id"]

    entities: list[tuple[str, str]] = [("PARTY", n) for n in payload.party_names]
    entities += [("ADDR", a) for a in payload.addresses]

    try:
        result = consulting.generate_consulting_analysis(
            matter_id,
            payload.question,
            limitation=payload.limitation.model_dump() if payload.limitation else None,
            forum=payload.forum.model_dump() if payload.forum else None,
            entities=entities,
            db=user.db,
        )
    except consulting.ConsultingAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"All LLM providers failed: {exc}") from exc
    return result


@router.get("/matters/{matter_id}/analyses", response_model=list[ConsultingAnalysisOut])
def list_analyses(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """List all Consulting analysis versions for a matter, most recent
    first — the original question is version 1, each follow-up a later
    version, all within this same matter."""
    _get_matter_or_404(user, matter_id)
    return consulting.list_consulting_analyses(matter_id, user.db)
