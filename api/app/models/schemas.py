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
    model_routing: ModelRoutingOut | None = None
    generation_warning: str | None = None
    created_at: datetime
    notice: str = "AI-generated draft analysis for advocate review. Not legal advice. Not a pleading."


# --- Sprint 3.6 Phase 1/3/4: Pleading Architecture (structured plans only,
# not drafted pleadings — see ADR-011, migration 0015) -----------------------

class ModelRoutingOut(BaseModel):
    """Sprint 3.6 Phase 4 (TICKET-20/21): what the LLM Gateway actually
    did, made explicit rather than silently discoverable only by
    inspecting model_used after the fact."""
    requested_model: str  # top of the pool for this task_type, e.g. "gemini-2.5-pro"
    actual_provider: str
    actual_model: str
    degraded: bool  # True if actual_model != requested_model
    fallback_chain: list[str] = Field(default_factory=list)  # every attempt tried, in order, incl. failures


class LegalIssueOut(BaseModel):
    issue: str
    related_cause_of_action: str | None = None  # links to a CauseOfActionOut.title, if applicable


class ReliefSoughtOut(BaseModel):
    relief: str
    basis: str  # which cause of action / statute this relief flows from


class EvidenceMappingItemOut(BaseModel):
    exhibit_number: str | None = None
    fact_summary: str
    supports: list[str] = Field(default_factory=list)  # cause-of-action / relief titles this evidence supports
    has_evidence_file: bool = False


class PleadingOutlineSectionOut(BaseModel):
    """One planned section of the eventual pleading — a content plan, not
    drafted prose. Enforced in code (pleading_outline.py), not just by
    convention: see _validate_outline_is_structured()."""
    section: str  # e.g. "Parties", "Facts", "Cause of Action", "Reliefs Sought"
    content_plan: str  # what this section will need to cover — a plan, never the pleading text itself


class PleadingOutlineGenerateRequest(BaseModel):
    case_analysis_id: str  # must reference an existing litigation_case_analyses row for this matter


class PleadingOutlineOut(BaseModel):
    id: str
    matter_id: str
    case_analysis_id: str
    version_no: int
    legal_issues: list[LegalIssueOut]
    applicable_statutes: list[ApplicableStatuteOut]
    applicable_case_law: list[PrecedentMentionOut]
    cause_of_action: list[CauseOfActionOut]
    reliefs_sought: list[ReliefSoughtOut]
    jurisdiction_summary: CaseAnalysisForumInput | None = None
    limitation_summary: CaseAnalysisLimitationInput | None = None
    evidence_mapping: list[EvidenceMappingItemOut]
    pleading_outline: list[PleadingOutlineSectionOut]
    model_used: str | None = None
    model_routing: ModelRoutingOut | None = None
    generation_warning: str | None = None
    created_at: datetime
    notice: str = (
        "AI-generated structured pleading PLAN for advocate review. "
        "Not legal advice. Not a drafted pleading — no prose pleading text "
        "has been generated from this outline."
    )


# --- Sprint 3.6 Phase 2: Clause-Based Drafting Engine ------------------------

class ClauseGenerateRequest(BaseModel):
    pleading_outline_id: str


class ClauseStatuteRefOut(BaseModel):
    act: str
    section_no: str
    grounded: bool


class ClauseCaseLawRefOut(BaseModel):
    case_name: str
    status: str  # 'verified' | 'not_in_verified_outline' — never a freshly-proposed, unverified name
    ik_url: str | None = None
    court: str | None = None


class ClauseGroundOut(BaseModel):
    """Sprint 3.6 Phase 2A (TICKET-25): one entry per reviewed legal issue,
    only ever populated for clause_type='legal_grounds'. Deliberately
    explicit per-field, not folded into free text — WORK ITEM 4's "every
    generated legal ground must explicitly identify issue/statute/section/
    precedent/confidence; if unavailable, say so" is satisfied by this
    shape existing at all, not inferred from prose after the fact."""
    issue: str
    statute_refs: list[ClauseStatuteRefOut]
    case_law_refs: list[ClauseCaseLawRefOut]
    argument_note: str
    confidence: float


class ClauseContentOut(BaseModel):
    text: str
    bullet_items: list[str] | None = None
    grounds: list[ClauseGroundOut] | None = None


class PleadingClauseOut(BaseModel):
    id: str
    matter_id: str
    pleading_outline_id: str
    clause_type: str
    version_no: int
    content: ClauseContentOut
    statute_refs: list[ClauseStatuteRefOut]
    case_law_refs: list[ClauseCaseLawRefOut]
    confidence: float
    is_deterministic: bool
    model_used: str | None = None
    model_routing: ModelRoutingOut | None = None
    prompt_version: str
    regenerated: bool
    author: str
    review_status: str  # 'pending' | 'approved' | 'rejected'
    reviewed_at: datetime | None = None
    generation_warning: str | None = None
    created_at: datetime
    notice: str = "AI-generated draft clause for advocate review. Not legal advice."


class ClauseReviewRequest(BaseModel):
    review_status: str = Field(pattern="^(approved|rejected)$")


class ComposePleadingRequest(BaseModel):
    pleading_outline_id: str


class ComposedSectionOut(BaseModel):
    paragraph_no: int
    clause_type: str
    heading: str
    text: str
    bullet_items: list[str] | None = None
    statute_refs: list[ClauseStatuteRefOut]
    case_law_refs: list[ClauseCaseLawRefOut]
    confidence: float | None = None


class ClauseVersionRefOut(BaseModel):
    clause_type: str
    clause_id: str
    version_no: int
    model_used: str | None = None
    prompt_version: str | None = None


class PleadingDraftOut(BaseModel):
    id: str
    matter_id: str
    pleading_outline_id: str
    version_no: int
    clause_versions: list[ClauseVersionRefOut]
    composed_sections: list[ComposedSectionOut]
    missing_clauses: list[str]
    created_at: datetime
    notice: str = (
        "AI-assisted DRAFT pleading composed from advocate-approved clauses only. "
        "Not legal advice. Advocate must review the full document before filing."
    )



# --- RERA & Real Estate (Phase 1 backend) ------------------------------------
# Property deeds and RERA complaints deliberately have NO dedicated models
# here beyond what's needed for state/walkthrough data — they reuse the
# existing GenerateDraftRequest/DraftOut (contracts router) and
# MatterCreate/MatterOut wholesale, exactly like any Contracts template.
# See docs/30_Implementation/RERA_BACKEND_INTEGRATION_CONTRACT.md for the
# full reuse rationale. Only the two capabilities with no existing
# equivalent — state/procedure/step content and walkthrough progress —
# get new models.

# ADR-010: Phase 1 supports Delhi, Maharashtra, Uttar Pradesh only. Any
# other state falls back to "unsupported — verify manually" rather than
# a guess, consistent with every other state-scoped feature in this
# project (jurisdiction selectors, state_rules lookups).
RERA_PHASE1_STATES = ("Delhi", "Maharashtra", "Uttar Pradesh")


class RERAStateRuleOut(BaseModel):
    """Mirrors contracts.py router's inline StateRuleOut shape (kept as a
    separate model rather than importing that router's private class —
    routers should not import from other routers) with the addition of
    verification_status (migration 0019)."""

    state: str
    instrument: str
    stamp_duty: str | None
    registration_req: str | None
    notes: str | None
    source_url: str | None
    last_verified: str | None
    verification_status: str = "unverified"


class RERAWalkthroughStepOut(BaseModel):
    id: str
    state: str
    procedure: str
    step_no: int
    heading: str | None = None
    instruction: str
    required_documents: list[str] = Field(default_factory=list)
    portal_url: str | None = None
    warnings: str | None = None
    source_url: str | None = None
    last_verified: str | None = None
    verification_status: str = "unverified"


class RERAWalkthroughProcedureOut(BaseModel):
    state: str
    procedure: str
    step_count: int


class RERAWalkthroughProgressOut(BaseModel):
    id: str
    user_id: str
    matter_id: str | None = None
    state: str
    procedure: str
    current_step_no: int
    completed_step_ids: list[str] = Field(default_factory=list)
    is_complete: bool
    started_at: datetime
    updated_at: datetime


class RERAWalkthroughProgressUpdate(BaseModel):
    """Advance/rewind or mark a step complete. `matter_id`, when given,
    associates this progress with a specific RERA matter — validated by
    the router to belong to the caller and to have module='rera' before
    any write happens (never trusted from the request body alone)."""

    matter_id: str | None = None
    current_step_no: int | None = Field(default=None, ge=1)
    mark_step_complete_id: str | None = None
    mark_step_incomplete_id: str | None = None
