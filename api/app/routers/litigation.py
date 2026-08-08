from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.auth import CurrentUser, get_current_user
from app.db import service_client
from app.models.schemas import (
    CaseAnalysisGenerateRequest,
    CaseAnalysisOut,
    ForumAdvisorRequest,
    ForumAdvisorResponse,
    LimitationRequest,
    LimitationResponse,
    LitigationFactCreate,
    LitigationFactOut,
    LitigationHearingCreate,
    LitigationHearingOut,
    LitigationMatterUpdate,
    LitigationPartyCreate,
    LitigationPartyOut,
    MatterOut,
)
from app.services import case_analysis, forum, limitation, litigation
from app.services.llm_gateway import ProviderError

router = APIRouter(prefix="/api", tags=["litigation"])

# Evidence file uploads: same size/type ceiling family as profile.py's
# avatar upload, widened for document exhibits (PDFs, scans) rather than
# photo-only. 10MB keeps this comfortably inside Render/Supabase free-tier
# request and storage limits for a single-user tool.
_ALLOWED_EVIDENCE_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_EVIDENCE_BYTES = 10 * 1024 * 1024


@router.post("/litigation/limitation-calculator", response_model=LimitationResponse)
def calculate_limitation(
    payload: LimitationRequest,
    _user: CurrentUser = Depends(get_current_user),
):
    """Deterministically calculate limitation expiry date and statutory status under Limitation Act, 1963."""
    try:
        return limitation.calculate_limitation(
            cause_of_action_date_str=payload.cause_of_action_date,
            suit_category=payload.suit_category,
            exclusion_days=payload.exclusion_days,
            selected_article=payload.selected_article,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/litigation/forum-advisor", response_model=ForumAdvisorResponse)
def determine_forum(
    payload: ForumAdvisorRequest,
    _user: CurrentUser = Depends(get_current_user),
):
    """Deterministically calculate recommended forum, territorial and pecuniary jurisdiction under CPC 1908 and State Rules."""
    return forum.determine_forum(
        suit_type=payload.suit_type,
        claim_value_inr=payload.claim_value_inr,
        jurisdiction_state=payload.jurisdiction_state,
        defendant_residence_state=payload.defendant_residence_state,
        cause_of_action_location=payload.cause_of_action_location,
        property_location_state=payload.property_location_state,
    )


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    return resp.data[0]


@router.patch("/matters/{matter_id}/litigation", response_model=MatterOut)
def update_litigation_matter(
    matter_id: str,
    payload: LitigationMatterUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Update litigation-specific attributes on a matter (court category, CNR, bench, stage)."""
    _get_matter_or_404(user, matter_id)
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    res = user.db.table("matters").update(update_data).eq("id", matter_id).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to update matter")
    return res.data[0]


# --- Litigation Parties Endpoints ---

@router.get("/matters/{matter_id}/parties", response_model=list[LitigationPartyOut])
def list_parties(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """List all parties for a litigation matter."""
    _get_matter_or_404(user, matter_id)
    return litigation.list_parties(matter_id, user.db)


@router.post("/matters/{matter_id}/parties", response_model=LitigationPartyOut, status_code=status.HTTP_201_CREATED)
def add_party(
    matter_id: str,
    payload: LitigationPartyCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """Add a Petitioner, Respondent, Plaintiff, or Defendant to a matter."""
    _get_matter_or_404(user, matter_id)
    return litigation.add_party(matter_id, payload.model_dump(), user.db)


@router.delete("/matters/{matter_id}/parties/{party_id}")
def delete_party(matter_id: str, party_id: str, user: CurrentUser = Depends(get_current_user)):
    """Remove a party from a matter."""
    _get_matter_or_404(user, matter_id)
    success = litigation.delete_party(party_id, matter_id, user.db)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found or already deleted")
    return {"status": "deleted", "id": party_id}


# --- Facts & Evidence Endpoints ---

@router.get("/matters/{matter_id}/evidence", response_model=list[LitigationFactOut])
def list_evidence(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """List all chronological fact entries and exhibits for a matter."""
    _get_matter_or_404(user, matter_id)
    return litigation.list_evidence(matter_id, user.db)


@router.post("/matters/{matter_id}/evidence", response_model=LitigationFactOut, status_code=status.HTTP_201_CREATED)
def add_evidence(
    matter_id: str,
    payload: LitigationFactCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """Add a chronological fact entry or exhibit item to a matter."""
    _get_matter_or_404(user, matter_id)
    return litigation.add_evidence(matter_id, payload.model_dump(), user.db)


@router.delete("/matters/{matter_id}/evidence/{evidence_id}")
def delete_evidence(matter_id: str, evidence_id: str, user: CurrentUser = Depends(get_current_user)):
    """Delete a fact entry from a matter."""
    _get_matter_or_404(user, matter_id)
    success = litigation.delete_evidence(evidence_id, matter_id, user.db)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence item not found")
    return {"status": "deleted", "id": evidence_id}


# --- Hearings & Docket Endpoints ---

@router.get("/matters/{matter_id}/hearings", response_model=list[LitigationHearingOut])
def list_hearings(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """List all scheduled and past hearings for a matter."""
    _get_matter_or_404(user, matter_id)
    return litigation.list_hearings(matter_id, user.db)


@router.post("/matters/{matter_id}/hearings", response_model=LitigationHearingOut, status_code=status.HTTP_201_CREATED)
def add_hearing(
    matter_id: str,
    payload: LitigationHearingCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """Log a court hearing date, IA number, purpose, or outcome."""
    _get_matter_or_404(user, matter_id)
    return litigation.add_hearing(matter_id, payload.model_dump(), user.db)


# --- Evidence File Upload (Sprint 3.5.3) ---------------------------------

@router.post("/matters/{matter_id}/evidence/upload", response_model=LitigationFactOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    matter_id: str,
    file: UploadFile = File(...),
    event_date: str | None = Form(None),
    exhibit_number: str | None = Form(None),
    document_title: str | None = Form(None),
    relevance_notes: str | None = Form(None),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload an actual exhibit/evidence document (not just a text label)
    and create the fact/evidence row for it in one step. Same upload
    pattern as profile.py's avatar upload: Supabase Storage bucket, with a
    non-fatal fallback path if the bucket isn't provisioned yet — evidence
    metadata is never lost even if the binary upload fails."""
    _get_matter_or_404(user, matter_id)

    if file.content_type not in _ALLOWED_EVIDENCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, DOC/DOCX, JPG, PNG, WEBP.",
        )

    content = await file.read()
    if len(content) > _MAX_EVIDENCE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds the 10MB maximum evidence upload size.",
        )

    file_ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    storage_path = f"evidence/{matter_id}/{uuid.uuid4()}.{file_ext}"

    try:
        svc = service_client()
        svc.storage.from_("evidence").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
        file_url = svc.storage.from_("evidence").get_public_url(storage_path)
    except Exception as exc:  # noqa: BLE001 — storage outage must not lose the evidence record
        file_url = None
        logging.getLogger("vidhidesk.litigation").warning(
            "upload_evidence storage upload failed, evidence row saved without file_url: %s", exc
        )

    payload = {
        "event_date": event_date or None,
        "fact_summary": relevance_notes or document_title or file.filename or "Uploaded evidence document",
        "exhibit_number": exhibit_number,
        "document_title": document_title or file.filename,
        "relevance_notes": relevance_notes,
        "file_url": file_url,
        "file_name": file.filename,
        "file_size_bytes": len(content),
        "mime_type": file.content_type,
    }
    return litigation.add_evidence(matter_id, payload, user.db)


# --- AI Case Analysis (Sprint 3.5.3) --------------------------------------

@router.post("/matters/{matter_id}/case-analysis", response_model=CaseAnalysisOut, status_code=status.HTTP_201_CREATED)
def generate_case_analysis(
    matter_id: str,
    payload: CaseAnalysisGenerateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Generate a new versioned AI Case Analysis for a litigation matter —
    a pre-drafting review, explicitly not a pleading. Reuses the Matter
    Engine, RAG Retriever, Limitation Engine and Forum Advisor output
    (passed through from the caller's already-computed results), LLM
    Gateway, and Citation Verifier. See app/services/case_analysis.py for
    the deterministic-vs-LLM trust boundary this endpoint enforces."""
    _get_matter_or_404(user, matter_id)
    try:
        result = case_analysis.generate_case_analysis(
            matter_id,
            limitation=payload.limitation.model_dump() if payload.limitation else None,
            forum=payload.forum.model_dump() if payload.forum else None,
            db=user.db,
        )
    except case_analysis.CaseAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"All LLM providers failed: {exc}") from exc
    return result


@router.get("/matters/{matter_id}/case-analysis", response_model=list[CaseAnalysisOut])
def list_case_analyses(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """List all AI Case Analysis versions for a matter, most recent first."""
    _get_matter_or_404(user, matter_id)
    return case_analysis.list_case_analyses(matter_id, user.db)
