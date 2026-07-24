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


class MatterOut(BaseModel):
    id: str
    title: str
    client_name: str | None
    module: str
    created_at: datetime


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
