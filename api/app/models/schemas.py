from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

MODULES = ("litigation", "contracts", "rera", "consulting")

# TRD §3.1 maps each module to its own system prompt in the LLM gateway.
MODULE_TASK_TYPE = {
    "litigation": "litigation_analyst",
    "contracts": "contract_drafter",
    "rera": "rera_specialist",
    "consulting": "consulting_analyst",
}


class MatterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    client_name: str | None = None
    module: str = Field(pattern="^(litigation|contracts|rera|consulting)$")
    template_id: str | None = None


class MatterOut(BaseModel):
    id: str
    title: str
    client_name: str | None
    module: str
    template_id: str | None = None
    created_at: datetime


class MatterUpdate(BaseModel):
    # Title-only for now — the auto-generating-title UX (Sprint 2 Phase 1
    # Session 1) needs a way to save the inferred title as party names
    # fill in, and to save a manual override on click-to-edit.
    title: str = Field(min_length=1, max_length=200)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    # Optional: known-sensitive entities the caller wants force-masked in
    # addition to the automatic PAN/Aadhaar/phone/email regex detection.
    party_names: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    model_used: str | None
    created_at: datetime
