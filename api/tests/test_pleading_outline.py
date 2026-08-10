from __future__ import annotations

from typing import Any

from app.services import pleading_outline
from app.services.citations import CitationRecord
from app.services.llm_gateway import GenerationResult, ProviderError


# --- Fake DB (same shape/convention as test_case_analysis.py's DummyDBClient) ---

class DummyDBTable:
    def __init__(self, table_name: str, store: dict[str, list[dict]]):
        self.table_name = table_name
        self.store = store
        self._where_clause: dict[str, Any] = {}

    def select(self, *args, **kwargs):
        return self

    def insert(self, row_data: dict | list[dict]):
        items = row_data if isinstance(row_data, list) else [row_data]
        inserted = []
        for item in items:
            record = dict(item)
            if "id" not in record:
                import uuid

                record["id"] = str(uuid.uuid4())
            if "created_at" not in record:
                from datetime import datetime, timezone

                record["created_at"] = datetime.now(timezone.utc).isoformat()
            self.store.setdefault(self.table_name, []).append(record)
            inserted.append(record)
        self._inserted_data = inserted
        return self

    def eq(self, column: str, value: Any):
        self._where_clause[column] = value
        return self

    def order(self, column: str, desc: bool = False, **kwargs):
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def execute(self):
        class DummyResp:
            def __init__(self, data):
                self.data = data

        if hasattr(self, "_inserted_data"):
            data = self._inserted_data
            del self._inserted_data
            return DummyResp(data)

        records = self.store.get(self.table_name, [])
        filtered = [r for r in records if all(r.get(k) == v for k, v in self._where_clause.items())]
        if getattr(self, "_order_col", None):
            filtered = sorted(filtered, key=lambda r: r.get(self._order_col) or 0, reverse=getattr(self, "_order_desc", False))
        if getattr(self, "_limit", None):
            filtered = filtered[: self._limit]
        return DummyResp(filtered)


class DummyDBClient:
    def __init__(self):
        self.store: dict[str, list[dict]] = {
            "matters": [],
            "litigation_parties": [],
            "litigation_facts_evidence": [],
            "litigation_case_analyses": [],
            "litigation_pleading_outlines": [],
        }

    def table(self, name: str):
        return DummyDBTable(name, self.store)


def _seed_matter(db: DummyDBClient) -> str:
    row = db.table("matters").insert(
        {"user_id": "user-123", "title": "Test Matter", "module": "litigation", "jurisdiction_state": "Delhi"}
    ).execute().data[0]
    return row["id"]


def _seed_party(db: DummyDBClient, matter_id: str):
    db.table("litigation_parties").insert(
        {"matter_id": matter_id, "party_type": "Petitioner", "party_name": "Ramesh Kumar", "party_number": 1}
    ).execute()


def _seed_case_analysis(db: DummyDBClient, matter_id: str, **overrides) -> str:
    row = {
        "matter_id": matter_id,
        "version_no": 1,
        "matter_summary": "A breach of contract dispute between Ramesh Kumar and the respondent.",
        "chronological_facts": [
            {"event_date": "2026-01-15", "fact_summary": "Agreement executed", "exhibit_number": "P-1", "has_evidence_file": True}
        ],
        "applicable_statutes": [
            {"act": "Indian Contract Act, 1872", "section_no": "73", "year": 1872, "chunk_excerpt": "Compensation for breach.", "score": 1.5}
        ],
        "possible_causes_of_action": [
            {"title": "Breach of Contract", "description": "Respondent failed to perform.", "supporting_facts": [], "statutes_relied_upon": []}
        ],
        "jurisdiction_summary": {"recommended_forum": {"forum_name": "Civil Judge Court, Delhi", "court_category": "District Courts", "territorial_basis": "x", "pecuniary_basis": "x", "governing_provisions": [], "confidence": "Deterministic", "assumptions": []}, "is_unambiguous": True},
        "limitation_summary": {"limitation_expiry_date": "2028-01-15", "is_barred": False, "days_remaining": 500, "primary_article": {"article_no": "55", "description": "x", "period": "3 years", "trigger_event": "x"}, "condonation_required": False, "condonation_notes": "x"},
    }
    row.update(overrides)
    return db.table("litigation_case_analyses").insert(row).execute().data[0]["id"]


def _fake_generate_factory(json_text: str):
    def _fake_generate(prompt, task_type="chat", mask_map=None, entities=None, **kwargs):
        assert task_type == "pleading_planner"
        assert entities is not None  # PII masking entities must always be passed
        return GenerationResult(
            text=json_text, provider="test", model="test-model", latency_ms=1, masked_prompt=prompt,
            requested_model="gemini-2.5-pro", degraded=True, fallback_chain=["gemini:gemini-2.5-pro (1/4)"],
        )

    return _fake_generate


VALID_JSON = """{
  "legal_issues": [{"issue": "Whether the agreement was validly breached", "related_cause_of_action": "Breach of Contract"}],
  "cause_of_action": [
    {"title": "Breach of Contract", "description": "Respondent failed to perform under the agreement.",
     "supporting_facts": ["Agreement executed"],
     "statutes_relied_upon": [{"act": "Indian Contract Act, 1872", "section_no": "73"}, {"act": "Made Up Act", "section_no": "999"}]}
  ],
  "reliefs_sought": [{"relief": "Recovery of Rs.5,00,000 with interest", "basis": "Breach of Contract"}],
  "evidence_mapping": [{"exhibit_number": "P-1", "fact_summary": "Agreement executed", "supports": ["Breach of Contract"], "has_evidence_file": true}],
  "pleading_outline": [
    {"section": "Cause Title / Parties", "content_plan": "Name both parties and their addresses."},
    {"section": "Jurisdiction", "content_plan": "State territorial and pecuniary basis per the Forum Advisor."},
    {"section": "Limitation", "content_plan": "State the limitation position per the Limitation Calculator."},
    {"section": "Facts Constituting the Cause of Action", "content_plan": "Narrate the agreement and breach chronologically."},
    {"section": "Cause of Action", "content_plan": "Plead breach of contract under Section 73."},
    {"section": "Valuation and Court Fees", "content_plan": "State claim value for jurisdiction and court-fee purposes."},
    {"section": "Reliefs Sought", "content_plan": "Pray for recovery of the principal with interest and costs."},
    {"section": "Verification", "content_plan": "Standard verification clause by the plaintiff."},
    {"section": "Made Up Section", "content_plan": "This section name was never in the fixed list."}
  ],
  "applicable_case_law": [{"case_name": "Ramesh Kumar vs State of Delhi", "note": "Similar fact pattern"}]
}"""


def _mock_verify_citation(case_name, db=None):
    return CitationRecord(
        case_name=case_name, neutral_citation=None, court="Delhi HC", status="verified",
        ik_doc_id="12345", ik_url="https://indiankanoon.org/doc/12345/", decided_on="2020-01-01",
        stale=False, from_cache=False,
    )


def test_generate_pleading_outline_requires_valid_case_analysis():
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    try:
        pleading_outline.generate_pleading_outline(matter_id, "nonexistent-id", db)
        assert False, "expected PleadingOutlineError"
    except pleading_outline.PleadingOutlineError as exc:
        assert "not found" in str(exc).lower()


def test_generate_pleading_outline_rejects_non_litigation_matter():
    db = DummyDBClient()
    row = db.table("matters").insert({"user_id": "u", "title": "T", "module": "contracts"}).execute().data[0]
    try:
        pleading_outline.generate_pleading_outline(row["id"], "some-id", db)
        assert False, "expected PleadingOutlineError"
    except pleading_outline.PleadingOutlineError as exc:
        assert "litigation" in str(exc).lower()


def test_generate_pleading_outline_happy_path(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    ca_id = _seed_case_analysis(db, matter_id)

    monkeypatch.setattr(pleading_outline, "generate", _fake_generate_factory(VALID_JSON))
    monkeypatch.setattr(pleading_outline, "verify_citation", _mock_verify_citation)

    result = pleading_outline.generate_pleading_outline(matter_id, ca_id, db)

    assert result["version_no"] == 1
    assert result["case_analysis_id"] == ca_id
    # passthrough sections come from the case analysis row verbatim, never re-derived
    assert result["jurisdiction_summary"]["recommended_forum"]["forum_name"] == "Civil Judge Court, Delhi"
    assert result["limitation_summary"]["limitation_expiry_date"] == "2028-01-15"
    assert result["applicable_statutes"][0]["act"] == "Indian Contract Act, 1872"

    # statute grounding cross-check: real statute grounded, invented one flagged
    refs = result["cause_of_action"][0]["statutes_relied_upon"]
    grounded = {r["section_no"]: r["grounded"] for r in refs}
    assert grounded["73"] is True
    assert grounded["999"] is False

    # citation verifier actually ran for applicable_case_law
    case_law = result["applicable_case_law"][0]
    assert case_law["status"] == "verified"
    assert case_law["ik_url"] == "https://indiankanoon.org/doc/12345/"

    # fixed-section enforcement: exactly 8 sections, in the fixed order, invented section dropped
    sections = [s["section"] for s in result["pleading_outline"]]
    assert sections == pleading_outline.FIXED_PLEADING_SECTIONS
    assert "Made Up Section" not in sections

    # model routing transparency (Phase 4) recorded explicitly
    assert result["model_used"] == "test/test-model"
    assert result["model_routing"]["requested_model"] == "gemini-2.5-pro"
    assert result["model_routing"]["degraded"] is True

    assert result["legal_issues"][0]["issue"]
    assert result["reliefs_sought"][0]["relief"]
    assert result["evidence_mapping"][0]["exhibit_number"] == "P-1"


def test_generate_pleading_outline_fills_missing_fixed_sections():
    """If the model omits a fixed section entirely, the outline still
    contains all 8 — never a silently missing section."""
    partial_json = VALID_JSON.replace(
        '{"section": "Verification", "content_plan": "Standard verification clause by the plaintiff."},', ""
    )
    db = DummyDBClient()
    matter_id = "m1"
    db.table("matters").insert({"id": matter_id, "user_id": "u", "title": "T", "module": "litigation"}).execute()
    _seed_party(db, matter_id)
    ca_id = _seed_case_analysis(db, matter_id)

    cleaned, warning = pleading_outline._validate_outline_is_structured(
        pleading_outline._extract_json(partial_json)["pleading_outline"]
    )
    sections = [s["section"] for s in cleaned]
    assert sections == pleading_outline.FIXED_PLEADING_SECTIONS
    verification = next(s for s in cleaned if s["section"] == "Verification")
    assert verification["content_plan"] == "(not yet planned by the model)"


def test_validate_outline_truncates_oversized_content_plan():
    oversized = "x" * 1000
    outline = [{"section": s, "content_plan": oversized if s == "Reliefs Sought" else "short note"} for s in pleading_outline.FIXED_PLEADING_SECTIONS]
    cleaned, warning = pleading_outline._validate_outline_is_structured(outline)
    reliefs = next(s for s in cleaned if s["section"] == "Reliefs Sought")
    assert len(reliefs["content_plan"]) <= pleading_outline.MAX_CONTENT_PLAN_CHARS + 60
    assert "truncated" in reliefs["content_plan"].lower()
    assert warning is not None


def test_generate_pleading_outline_regeneration_increments_version(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    ca_id = _seed_case_analysis(db, matter_id)

    monkeypatch.setattr(pleading_outline, "generate", _fake_generate_factory(VALID_JSON))
    monkeypatch.setattr(pleading_outline, "verify_citation", _mock_verify_citation)

    first = pleading_outline.generate_pleading_outline(matter_id, ca_id, db)
    second = pleading_outline.generate_pleading_outline(matter_id, ca_id, db)
    assert first["version_no"] == 1
    assert second["version_no"] == 2


def test_generate_pleading_outline_handles_malformed_llm_json_without_crashing(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    ca_id = _seed_case_analysis(db, matter_id)

    monkeypatch.setattr(pleading_outline, "generate", _fake_generate_factory("not json at all"))
    monkeypatch.setattr(pleading_outline, "verify_citation", _mock_verify_citation)

    result = pleading_outline.generate_pleading_outline(matter_id, ca_id, db)
    assert result["generation_warning"]
    assert result["cause_of_action"] == []  # degraded result, never a crash
    # even on a fully malformed response, every fixed section still appears —
    # "not yet planned," never silently missing
    assert [s["section"] for s in result["pleading_outline"]] == pleading_outline.FIXED_PLEADING_SECTIONS
    assert all(s["content_plan"] == "(not yet planned by the model)" for s in result["pleading_outline"])


def test_generate_pleading_outline_propagates_provider_error_when_all_llm_providers_fail(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    ca_id = _seed_case_analysis(db, matter_id)

    def _boom(*a, **k):
        raise ProviderError("all", "every provider failed")

    monkeypatch.setattr(pleading_outline, "generate", _boom)
    try:
        pleading_outline.generate_pleading_outline(matter_id, ca_id, db)
        assert False, "expected ProviderError to propagate"
    except ProviderError:
        pass
