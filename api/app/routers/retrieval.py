from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.services.retrieval import hybrid_retrieve

router = APIRouter(prefix="/api", tags=["retrieval"])


class RetrieveRequest(BaseModel):
    facts: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievedChunkOut(BaseModel):
    score: float
    act: str
    section_no: str
    year: int | None
    chunk_text: str


@router.post("/retrieve", response_model=list[RetrievedChunkOut])
def retrieve(body: RetrieveRequest, _user: CurrentUser = Depends(get_current_user)):
    results = hybrid_retrieve(body.facts, top_k=body.top_k)
    return [
        RetrievedChunkOut(
            score=c.score, act=c.act, section_no=c.section_no, year=c.year, chunk_text=c.chunk_text
        )
        for c in results
    ]
