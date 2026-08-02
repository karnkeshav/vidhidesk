from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.services import contracts
from app.services.llm_gateway import ProviderError

router = APIRouter(prefix="/api", tags=["contracts"])
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        # RLS makes another user's matter look identical to a missing one —
        # that's the point: no ownership-probing oracle.
        raise HTTPException(status_code=404, detail="Matter not found")
    return resp.data[0]


class TemplateOut(BaseModel):
    id: str
    name: str
    category: str
    review_status: str
    states_supported: list[str]
    template_key: str | None = None


class TemplateDetailOut(TemplateOut):
    # Named intake_schema, not schema_json (the DB column name) — pydantic
    # BaseModel has its own deprecated schema_json() method, and a field of
    # the same name shadows it with a warning.
    intake_schema: dict


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(user: CurrentUser = Depends(get_current_user)):
    rows = (
        user.db.table("templates")
        .select("id,name,category,review_status,states_supported,template_key")
        .order("name")
        .execute()
        .data
        or []
    )
    return rows


@router.get("/templates/{template_id}", response_model=TemplateDetailOut)
def get_template(template_id: str, user: CurrentUser = Depends(get_current_user)):
    rows = user.db.table("templates").select("*").eq("id", template_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Template not found")
    row = rows[0]
    return TemplateDetailOut(
        id=row["id"], name=row["name"], category=row["category"],
        review_status=row["review_status"], states_supported=row["states_supported"],
        template_key=row.get("template_key"), intake_schema=row["schema_json"],
    )


class StateRuleOut(BaseModel):
    state: str
    instrument: str
    stamp_duty: str | None
    registration_req: str | None
    notes: str | None
    source_url: str | None
    last_verified: str | None


@router.get("/state-rules", response_model=list[StateRuleOut])
def get_state_rules(
    state: str, instrument: str, user: CurrentUser = Depends(get_current_user)
):
    """Backs the intake form's live state-law-notes panel (TRD §3.4) — the
    lawyer sees stamp-duty/registration notes for the chosen state as soon
    as they pick it, not just after the draft is generated."""
    rows = (
        user.db.table("state_rules")
        .select("*")
        .eq("state", state)
        .eq("instrument", instrument)
        .execute()
        .data
        or []
    )
    return rows


class GenerateDraftRequest(BaseModel):
    template_id: str
    form_data: dict
    amendment_note: str | None = None


class ClauseFillOut(BaseModel):
    clause_key: str
    generated_text: str
    model_used: str


class DraftOut(BaseModel):
    draft_version_id: str
    version_no: int
    docx_path: str
    clause_fills: list[ClauseFillOut]
    full_text: str


@router.post("/matters/{matter_id}/drafts", response_model=DraftOut, status_code=201)
def generate_draft(
    matter_id: str, body: GenerateDraftRequest, user: CurrentUser = Depends(get_current_user)
):
    """Generate (or, called again with updated form_data, re-generate as a
    new version of) a draft for this matter. Ownership of the matter is
    checked here, via the caller's RLS-scoped client, before handing off
    to the service layer — see app/db.py on why service-role writes are
    safe once that check has passed."""
    _get_matter_or_404(user, matter_id)
    try:
        result = contracts.generate_draft(
            matter_id, body.template_id, body.form_data, amendment_note=body.amendment_note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=f"All LLM providers failed: {exc}") from exc

    return DraftOut(
        draft_version_id=result.draft_version_id,
        version_no=result.version_no,
        docx_path=result.docx_path,
        clause_fills=[
            ClauseFillOut(
                clause_key=f.clause_key, generated_text=f.generated_text, model_used=f.model_used
            )
            for f in result.clause_fills
        ],
        full_text=result.full_text,
    )


class DraftVersionOut(BaseModel):
    id: str
    template_id: str
    version_no: int
    docx_path: str
    change_summary: str | None
    created_at: str


@router.get("/matters/{matter_id}/drafts", response_model=list[DraftVersionOut])
def list_drafts(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """Version history for the amendment loop (AC-2.3) — newest first."""
    _get_matter_or_404(user, matter_id)
    return contracts.list_drafts(matter_id, db=user.db)


def _get_draft_or_404(user: CurrentUser, draft_version_id: str) -> dict:
    # draft_versions has the same owner-only RLS policy as matters
    # (migrations/0002_rls.sql) — a non-owned draft looks like a missing
    # one to the caller's RLS-scoped client, same 404-not-403 posture as
    # _get_matter_or_404 above.
    draft = contracts.get_draft(draft_version_id, db=user.db)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("/drafts/{draft_version_id}/download")
def download_draft_docx(draft_version_id: str, user: CurrentUser = Depends(get_current_user)):
    draft = _get_draft_or_404(user, draft_version_id)
    path = REPO_ROOT / draft["docx_path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Draft file missing on disk")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


@router.get("/drafts/{draft_version_id}/download.pdf")
def download_draft_pdf(draft_version_id: str, user: CurrentUser = Depends(get_current_user)):
    draft = _get_draft_or_404(user, draft_version_id)
    docx_path = REPO_ROOT / draft["docx_path"]
    if not docx_path.exists():
        raise HTTPException(status_code=404, detail="Draft file missing on disk")
    try:
        pdf_path = contracts.convert_docx_to_pdf(docx_path)
    except contracts.PdfConversionUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


class TemplateClauseOut(BaseModel):
    id: str
    clause_key: str
    display_order: int
    clause_type: str
    applicable_condition: dict | None
    heading: str | None
    current_text: str
    review_status: str


@router.get("/templates/{template_id}/clauses", response_model=list[TemplateClauseOut])
def get_template_clauses(template_id: str, user: CurrentUser = Depends(get_current_user)):
    """Backs the clause-review UX (Project_Plan §6.2): the ordered clause
    list for a template, with each clause's current review status."""
    return contracts.list_clauses(template_id, db=user.db)


class ClauseReviewRequest(BaseModel):
    decision: str
    redraft_text: str | None = None
    reviewer_notes: str | None = None


@router.post("/templates/{template_id}/clauses/{clause_id}/review", response_model=TemplateClauseOut)
def review_clause(
    template_id: str,
    clause_id: str,
    body: ClauseReviewRequest,
    _user: CurrentUser = Depends(get_current_user),
):
    """Records one keep/redraft/delete decision. Writes go through the
    service role (RLS permits only reads on template_clauses/clause_reviews
    for the authenticated role — see migration 0007) since this is
    reference-data curation, not matter-owned data."""
    try:
        return contracts.review_clause(
            clause_id,
            body.decision,
            redraft_text=body.redraft_text,
            reviewer_notes=body.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/templates/{template_id}/clauses/bulk-keep-boilerplate",
    response_model=list[TemplateClauseOut],
)
def bulk_keep_boilerplate(template_id: str, _user: CurrentUser = Depends(get_current_user)):
    """Lever 1 (2026-08-02 review-velocity request): keep every currently-
    unreviewed fixed_boilerplate clause on a template in one action.
    Never touches llm_fillable clauses (those still need individual
    review — the generated content genuinely varies) or a clause that's
    already been reviewed (keep/redraft/delete), so it can't silently
    overwrite an existing human decision. Returns the updated clause
    rows, same shape as the per-clause review endpoint, empty list if
    nothing qualified."""
    return contracts.bulk_keep_boilerplate_clauses(template_id)
