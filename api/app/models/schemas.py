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
    court_category: str | None = None
    jurisdiction_state: str | None = None
    cnr_number: str | None = None
    case_number_formatted: str | None = None
    litigation_stage: str | None = None
    court_name: str | None = None
    bench_name: str | None = None


class MatterOut(BaseModel):
    id: str
    title: str
    client_name: str | None
    module: str
    template_id: str | None = None
    court_category: str | None = None
    jurisdiction_state: str | None = None
    cnr_number: str | None = None
    case_number_formatted: str | None = None
    litigation_stage: str | None = None
    court_name: str | None = None
    bench_name: str | None = None
    created_at: datetime


class LitigationMatterUpdate(BaseModel):
    court_category: str | None = None
    jurisdiction_state: str | None = None
    cnr_number: str | None = None
    case_number_formatted: str | None = None
    litigation_stage: str | None = None
    court_name: str | None = None
    bench_name: str | None = None


class LitigationPartyCreate(BaseModel):
    party_type: str = Field(min_length=1, max_length=50)  # e.g., Petitioner, Respondent, Plaintiff, Defendant
    party_name: str = Field(min_length=1, max_length=200)
    party_number: int = 1
    address: str | None = None
    advocate_name: str | None = None


class LitigationPartyOut(BaseModel):
    id: str
    matter_id: str
    party_type: str
    party_name: str
    party_number: int
    address: str | None = None
    advocate_name: str | None = None
    created_at: datetime


class LitigationFactCreate(BaseModel):
    event_date: str | None = None  # YYYY-MM-DD format
    fact_summary: str = Field(min_length=1)
    exhibit_number: str | None = None
    document_title: str | None = None
    relevance_notes: str | None = None


class LitigationFactOut(BaseModel):
    id: str
    matter_id: str
    event_date: str | None = None
    fact_summary: str
    exhibit_number: str | None = None
    document_title: str | None = None
    relevance_notes: str | None = None
    file_url: str | None = None
    file_name: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    created_at: datetime


class LitigationHearingCreate(BaseModel):
    hearing_date: str = Field(min_length=1)  # YYYY-MM-DD format
    cause_list_item_no: int | None = None
    purpose_of_hearing: str | None = None
    ia_number: str | None = None
    hearing_outcome: str | None = None
    next_hearing_date: str | None = None
    status: str = "Scheduled"


class LitigationHearingOut(BaseModel):
    id: str
    matter_id: str
    hearing_date: str
    cause_list_item_no: int | None = None
    purpose_of_hearing: str | None = None
    ia_number: str | None = None
    hearing_outcome: str | None = None
    next_hearing_date: str | None = None
    status: str
    created_at: datetime


class LimitationCandidateArticle(BaseModel):
    article_number: str
    description: str
    statutory_period_years: float
    governing_act: str = "Limitation Act, 1963"
    trigger_event: str
    notes: str | None = None


class LimitationRequest(BaseModel):
    cause_of_action_date: str = Field(min_length=1)  # YYYY-MM-DD
    suit_category: str = Field(min_length=1)  # e.g., 'Money Recovery', 'Specific Performance', 'Possession', 'Declaratory', 'Breach of Contract', 'Appeal'
    exclusion_days: int = Field(default=0, ge=0)
    selected_article: str | None = None


class LimitationResponse(BaseModel):
    cause_of_action_date: str
    suit_category: str
    limitation_expiry_date: str
    is_barred: bool
    days_remaining: int
    primary_article: LimitationCandidateArticle
    candidate_articles: list[LimitationCandidateArticle]
    condonation_required: bool
    condonation_notes: str
    notice: str = "Rule-based statutory calculation under Limitation Act, 1963. Advocate vetting required."


class ForumAdvisorRequest(BaseModel):
    suit_type: str = Field(min_length=1)  # e.g., 'Civil Suit', 'Property Dispute', 'Commercial Dispute', 'RERA', 'Consumer'
    claim_value_inr: float = Field(ge=0)
    jurisdiction_state: str = Field(min_length=1)  # e.g., 'Delhi', 'Maharashtra', 'Karnataka', 'Tamil Nadu'
    defendant_residence_state: str | None = None
    cause_of_action_location: str | None = None
    property_location_state: str | None = None


class ForumOption(BaseModel):
    forum_name: str
    court_category: str
    territorial_basis: str
    pecuniary_basis: str
    governing_provisions: list[str]
    confidence: str  # 'Deterministic' | 'Manual Review Required'
    assumptions: list[str]


class ForumAdvisorResponse(BaseModel):
    recommended_forum: ForumOption
    viable_options: list[ForumOption]
    is_unambiguous: bool = True
    notice: str = "Rule-based statutory jurisdiction calculation under CPC 1908 & State Rules. Advocate vetting required."


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


class AdvocateProfile(BaseModel):
    user_id: str
    full_name: str | None = None
    designation: str = "Advocate"
    bar_number: str | None = None
    primary_court: str | None = None
    phone: str | None = None
    office_address: str | None = None
    avatar_url: str | None = None
    updated_at: datetime | None = None


class AdvocateProfileUpdate(BaseModel):
    full_name: str | None = None
    designation: str | None = "Advocate"
    bar_number: str | None = None
    primary_court: str | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[1-9]\d{1,14}$")
    office_address: str | None = None
    avatar_url: str | None = None


# --- AI Case Analysis (Sprint 3.5.3 vertical slice) -------------------------
# Deterministic input carried forward from a prior Limitation Engine /
# Forum Advisor call, verbatim — the analysis never re-derives (and risks
# re-deriving differently from) a conclusion those engines already computed.

class CaseAnalysisLimitationInput(BaseModel):
    limitation_expiry_date: str
    is_barred: bool
    days_remaining: int
    primary_article: LimitationCandidateArticle
    condonation_required: bool
    condonation_notes: str


class CaseAnalysisForumInput(BaseModel):
    recommended_forum: ForumOption
    is_unambiguous: bool


class CaseAnalysisGenerateRequest(BaseModel):
    limitation: CaseAnalysisLimitationInput | None = None
    forum: CaseAnalysisForumInput | None = None


class ChronologicalFactOut(BaseModel):
    event_date: str | None = None
    fact_summary: str
    exhibit_number: str | None = None
    has_evidence_file: bool = False


class ApplicableStatuteOut(BaseModel):
    act: str
    section_no: str
    year: int | None = None
    chunk_excerpt: str
    score: float


class CauseOfActionStatuteRef(BaseModel):
    act: str
    section_no: str
    grounded: bool  # True only if it matches a retrieved chunk — never trusted on the model's say-so


class CauseOfActionOut(BaseModel):
    title: str
    description: str
    supporting_facts: list[str] = Field(default_factory=list)
    statutes_relied_upon: list[CauseOfActionStatuteRef] = Field(default_factory=list)


class PotentialRiskOut(BaseModel):
    risk: str
    severity: str  # 'High' | 'Medium' | 'Low'
    mitigation: str | None = None


class PrecedentMentionOut(BaseModel):
    case_name: str
    note: str
    status: str  # 'verified' | 'unverified' — from the Citation Verifier, not the model's claim
    ik_url: str | None = None
    court: str | None = None


class CaseAnalysisOut(BaseModel):
    id: str
    matter_id: str
    version_no: int
    matter_summary: str
    chronological_facts: list[ChronologicalFactOut]
    missing_information: list[str]
    applicable_statutes: list[ApplicableStatuteOut]
    possible_causes_of_action: list[CauseOfActionOut]
    jurisdiction_summary: CaseAnalysisForumInput | None = None
    limitation_summary: CaseAnalysisLimitationInput | None = None
    potential_risks: list[PotentialRiskOut]
    evidence_gaps: list[str]
    recommended_next_steps: list[str]
    possible_precedents: list[PrecedentMentionOut]
    model_used: str | None = None
    generation_warning: str | None = None
    created_at: datetime
    notice: str = "AI-generated draft analysis for advocate review. Not legal advice. Not a pleading."

