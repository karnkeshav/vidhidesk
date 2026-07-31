from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.services.citation_render import render_citation_by_lookup

router = APIRouter(prefix="/api/citations", tags=["citations"])


class RenderCitationRequest(BaseModel):
    case_name: str
    neutral_citation: str | None = None


class RenderCitationResponse(BaseModel):
    renderable: bool
    url: str | None
    label: str
    html: str


@router.post("/render", response_model=RenderCitationResponse)
def render_citation_endpoint(
    body: RenderCitationRequest, _user: CurrentUser = Depends(get_current_user)
):
    """The only sanctioned way for the frontend to turn a citation into
    markup — it never inspects a citations row itself. See
    app/services/citation_render.py for the gate this enforces."""
    result = render_citation_by_lookup(body.case_name, body.neutral_citation)
    return RenderCitationResponse(
        renderable=result.renderable, url=result.url, label=result.label, html=result.html
    )
