from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.services import clause_generator
from app.services.citations import CitationRecord
from app.services.llm_gateway import GenerationResult, ProviderError


# --- Fake DB (same shape/convention as test_pleading_outline.py's
# DummyDBClient, extended with update() support for review_clause()) -----

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
                record["id"] = str(uuid.uuid4())
            if "created_at" not in record:
                record["created_at"] = datetime.now(timezone.utc).isoformat()
            self.store.setdefault(self.table_name, []).append(record)
            inserted.append(record)
        self._inserted_data = inserted
        return self

    def update(self, update_data: dict):
        self._update_data = update_data
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

        if hasattr(self, "_update_data"):
            update_data = self._update_data
            del self._update_data
            records = self.store.get(self.table_name, [])
            updated = []
            for r in records:
                if all(r.get(k) == v for k, v in self._where_clause.items()):
                    r.update(update_data)
                    updated.append(r)
            return DummyResp(updated)

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
            "litigation_case_analyses": [],
            "litigation_pleading_outlines": [],
            "litigation_pleading_clauses": [],
            "litigation_pleading_drafts": [],
        }

    def table(self, name: str):
        return DummyDBTable(name, self.store)


def _seed_matter(db: DummyDBClient, **overrides) -> str:
    row = {
        "user_id": "user-123", "title": "Ramesh Kumar vs State Bank", "module": "litigation",
        "jurisdiction_state": "Delhi", "court_name": "District Court, Saket",
        "case_number_formatted": "CS/123/2026",
    }
    row.update(overrides)
    return db.table("matters").insert(row).execute().data[0]["id"]


def _seed_parties(db: DummyDBClient, matter_id: str):
    db.table("litigation_parties").insert({
        "matter_id": matter_id, "party_type": "Plaintiff", "party_name": "Ramesh Kumar",
        "party_number": 1, "address": "123 MG Road, Delhi",
    }).execute()
    db.table("litigation_parties").insert({
        "matter_id": matter_id, "party_type": "Defendant", "party_name": "State Bank of India",
        "party_number": 1, "address": "Parliament Street, Delhi",
    }).execute()


def _seed_case_analysis(db: DummyDBClient, matter_id: str, **overrides) -> str:
    row = {
        "matter_id": matter_id,
        "version_no": 1,
        "matter_summary": "A breach of contract dispute.",
        "chronological_facts": [
            {"event_date": "2026-01-15", "fact_summary": "Agreement executed", "exhibit_number": "P-1", "has_evidence_file": True},
            {"event_date": "2026-03-01", "fact_summary": "Defendant failed to perform", "exhibit_number": None, "has_evidence_file": False},
        ],
    }
    row.update(overrides)
    return db.table("litigation_case_analyses").insert(row).execute().data[0]["id"]


def _seed_outline(db: DummyDBClient, matter_id: str, case_analysis_id: str, **overrides) -> str:
    row = {
        "matter_id": matter_id,
        "case_analysis_id": case_analysis_id,
        "version_no": 1,
        "jurisdiction_summary": {
            "recommended_forum": {
                "forum_name": "Civil Judge Court, Delhi", "court_category": "District Courts",
                "territorial_basis": "the cause of action arose within Delhi",
                "pecuniary_basis": "the claim value falls within the District Court's limit",
                "governing_provisions": ["Section 20, Code of Civil Procedure, 1908"],
                "confidence": "Deterministic", "assumptions": [],
            },
            "is_unambiguous": True,
        },
        "limitation_summary": {"limitation_expiry_date": "2029-01-15", "is_barred": False, "days_remaining": 900},
        "applicable_statutes": [
            {"act": "Indian Contract Act, 1872", "section_no": "73", "year": 1872, "chunk_excerpt": "Compensation for breach.", "score": 1.5},
        ],
        "legal_issues": [{"issue": "Whether the agreement was breached", "related_cause_of_action": "Breach of Contract"}],
        "cause_of_action": [
            {"title": "Breach of Contract", "description": "Defendant failed to perform.", "supporting_facts": ["Agreement executed"], "statutes_relied_upon": [{"act": "Indian Contract Act, 1872", "section_no": "73", "grounded": True}]},
        ],
        "reliefs_sought": [{"relief": "Recovery of Rs.5,00,000 with interest", "basis": "Breach of Contract"}],
        "evidence_mapping": [],
        "pleading_outline": [],
        "applicable_case_law": [
            {"case_name": "Fateh Chand vs Balkishan Dass", "note": "damages for breach", "status": "verified", "ik_url": "https://indiankanoon.org/doc/999/", "court": "Supreme Court"},
            {"case_name": "Some Unverified Case vs Another Party", "note": "n/a", "status": "unverified", "ik_url": None, "court": None},
        ],
    }
    row.update(overrides)
    return db.table("litigation_pleading_outlines").insert(row).execute().data[0]["id"]


def _seed_full_matter(db: DummyDBClient) -> tuple[str, str, str]:
    matter_id = _seed_matter(db)
    _seed_parties(db, matter_id)
    ca_id = _seed_case_analysis(db, matter_id)
    outline_id = _seed_outline(db, matter_id, ca_id)
    return matter_id, ca_id, outline_id


def _fake_generation_result(json_text: str, prompt: str) -> GenerationResult:
    return GenerationResult(
        text=json_text, provider="test", model="test-model", latency_ms=1, masked_prompt=prompt,
        requested_model="gemini-2.5-pro", degraded=True, fallback_chain=["gemini:gemini-2.5-pro (1/4)"],
    )


def _fake_generate_json_factory(json_text: str, task_type_expected: str = "clause_drafter"):
    """Sprint 3.6 Phase 2A: generate_clause()'s LLM path now calls
    llm_gateway.generate_json() (json_mode + one repair attempt), not raw
    generate() — this fakes that same (GenerationResult, parsed) contract."""
    import json as _json

    def _fake_generate_json(prompt, task_type="chat", mask_map=None, entities=None, **kwargs):
        assert task_type == task_type_expected
        assert entities is not None
        result = _fake_generation_result(json_text, prompt)
        try:
            parsed = _json.loads(json_text)
        except _json.JSONDecodeError:
            parsed = None
        return result, parsed
    return _fake_generate_json


VALID_CLAUSE_JSON = """{
  "content": "That the Plaintiff states as follows: the Defendant failed to perform the agreement dated 15 January 2026.",
  "statute_refs": [{"act": "Indian Contract Act, 1872", "section_no": "73"}, {"act": "Made Up Act", "section_no": "999"}],
  "case_law_refs": [{"case_name": "Fateh Chand vs Balkishan Dass"}, {"case_name": "Never Heard Of This Case"}],
  "confidence": 0.8
}"""

# Sprint 3.6 Phase 2A: legal_grounds's own, different response shape — a
# structured per-issue "grounds" list, not one free-form "content" string.
# See clause_generator._prompt_legal_grounds / _generate_legal_grounds.
VALID_LEGAL_GROUNDS_JSON = """{
  "grounds": [
    {
      "issue": "Whether the agreement was breached",
      "statute_refs": [{"act": "Indian Contract Act, 1872", "section_no": "73"}, {"act": "Made Up Act", "section_no": "999"}],
      "case_law_refs": [{"case_name": "Fateh Chand vs Balkishan Dass"}, {"case_name": "Never Heard Of This Case"}],
      "argument_note": "The Defendant's non-performance directly gives rise to a claim for compensation.",
      "confidence": 0.8
    }
  ]
}"""


# --- Deterministic clause generators -----------------------------------------

def test_deterministic_clause_types_never_call_llm(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("deterministic clause must never call generate()")
    monkeypatch.setattr(clause_generator, "generate_json", _boom)

    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    for clause_type in clause_generator.DETERMINISTIC_CLAUSE_TYPES:
        result = clause_generator.generate_clause(matter_id, outline_id, clause_type, db)
        assert result["is_deterministic"] is True
        assert result["confidence"] == 1.0
        assert result["model_used"] is None
        assert result["content"]["text"]


def test_cause_title_includes_both_parties():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    text = result["content"]["text"]
    assert "Ramesh Kumar" in text
    assert "State Bank of India" in text
    assert "VERSUS" in text


def test_applicable_statutes_clause_is_grounded_passthrough():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "applicable_statutes", db)
    assert result["statute_refs"] == [{"act": "Indian Contract Act, 1872", "section_no": "73", "grounded": True}]


def test_applicable_precedents_clause_only_includes_verified_case_law():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "applicable_precedents", db)
    case_names = [c["case_name"] for c in result["case_law_refs"]]
    assert case_names == ["Fateh Chand vs Balkishan Dass"]
    assert "Some Unverified Case vs Another Party" not in result["content"]["text"]


def test_verification_clause_uses_filing_party_name():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "verification", db)
    assert "Ramesh Kumar" in result["content"]["text"]


def test_jurisdiction_clause_deterministic_and_grounded():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "jurisdiction", db)
    assert result["is_deterministic"] is True
    assert "Civil Judge Court, Delhi" in result["content"]["text"]


# --- LLM clause generators ----------------------------------------------------

def test_llm_clause_types_call_generate_with_clause_drafter_task_type(monkeypatch):
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate_json_factory(VALID_CLAUSE_JSON))
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    for clause_type in ("facts", "cause_of_action", "reliefs", "prayer"):
        result = clause_generator.generate_clause(matter_id, outline_id, clause_type, db)
        assert result["is_deterministic"] is False
        assert result["model_used"] == "test/test-model"
        assert result["content"]["text"]


def test_legal_grounds_uses_its_own_structured_shape_and_generates_content(monkeypatch):
    """Sprint 3.6 Phase 2A (TICKET-25): legal_grounds no longer shares the
    generic {content, statute_refs, case_law_refs, confidence} shape — it
    gets a per-issue "grounds" list, and the final clause text is
    deterministically assembled from it (_assemble_legal_grounds_text), not
    trusted verbatim from the model."""
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate_json_factory(VALID_LEGAL_GROUNDS_JSON))
    monkeypatch.setattr(clause_generator, "verify_citation", lambda case_name, db=None: CitationRecord(
        case_name=case_name, neutral_citation=None, court=None, status="unverified",
        ik_doc_id=None, ik_url=None, decided_on=None, stale=False, from_cache=False,
    ))
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    result = clause_generator.generate_clause(matter_id, outline_id, "legal_grounds", db)
    assert result["is_deterministic"] is False
    assert result["model_used"] == "test/test-model"
    assert result["content"]["text"]
    assert "Whether the agreement was breached" in result["content"]["text"]
    assert len(result["content"]["grounds"]) == 1
    assert result["content"]["grounds"][0]["issue"] == "Whether the agreement was breached"


def test_llm_clause_statute_ref_grounding():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    ctx = clause_generator._clause_context(matter_id, outline_id, db)
    refs = clause_generator._ground_statute_refs(
        [{"act": "Indian Contract Act, 1872", "section_no": "73"}, {"act": "Made Up Act", "section_no": "999"}],
        ctx["grounded_acts"],
    )
    grounded = {r["section_no"]: r["grounded"] for r in refs}
    assert grounded["73"] is True
    assert grounded["999"] is False


def test_llm_clause_case_law_ref_never_trusts_unverified_or_unknown_names():
    """cause_of_action (still the generic single-call path): a clause
    generator's own claimed case_law_refs are cross-checked against the
    outline's already-verified applicable_case_law — a case the outline
    never verified must never come through this gate as citable (CLAUDE.md
    Hard Rule 1). See test_legal_grounds_* below for legal_grounds's own,
    additional live-verification behavior (Sprint 3.6 Phase 2A)."""
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    ctx = clause_generator._clause_context(matter_id, outline_id, db)
    refs = clause_generator._ground_case_law_refs(
        [{"case_name": "Fateh Chand vs Balkishan Dass"}, {"case_name": "Never Heard Of This Case"}],
        ctx["verified_case_law"],
    )
    by_name = {c["case_name"]: c for c in refs}
    assert by_name["Fateh Chand vs Balkishan Dass"]["status"] == "verified"
    assert by_name["Fateh Chand vs Balkishan Dass"]["ik_url"] == "https://indiankanoon.org/doc/999/"
    assert by_name["Never Heard Of This Case"]["status"] == "not_in_verified_outline"
    assert by_name["Never Heard Of This Case"]["ik_url"] is None


def test_legal_grounds_case_law_gets_one_live_verify_attempt_for_a_name_not_already_verified(monkeypatch):
    """Sprint 3.6 Phase 2A (TICKET-25): unlike every other LLM clause type,
    legal_grounds's own case_law_refs get ONE live Citation Verifier check
    (bounded, MAX_NEW_CASE_LAW_TO_VERIFY) for a name not already in the
    outline's verified pool — the concrete mechanism behind
    _prompt_legal_grounds's invitation to name a case not already on
    record. A name the live check confirms comes back "verified" with a
    real IK URL; one it can't confirm comes back "unverified" — never
    silently trusted either way (CLAUDE.md Hard Rule 1)."""
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate_json_factory(VALID_LEGAL_GROUNDS_JSON))
    calls: list[str] = []

    def _fake_verify_citation(case_name, db=None):
        calls.append(case_name)
        return CitationRecord(
            case_name=case_name, neutral_citation=None, court="Supreme Court", status="verified",
            ik_doc_id="12345", ik_url="https://indiankanoon.org/doc/12345/", decided_on="1999-01-01",
            stale=False, from_cache=False,
        )
    monkeypatch.setattr(clause_generator, "verify_citation", _fake_verify_citation)

    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "legal_grounds", db)

    # "Fateh Chand vs Balkishan Dass" is already in the outline's verified
    # pool -> must NOT trigger a live call (cache-first, same as every
    # other module in this pipeline).
    assert "Fateh Chand vs Balkishan Dass" not in calls
    # "Never Heard Of This Case" is not in the outline's pool -> gets the
    # one live check.
    assert calls == ["Never Heard Of This Case"]

    by_name = {c["case_name"]: c for c in result["case_law_refs"]}
    assert by_name["Fateh Chand vs Balkishan Dass"]["status"] == "verified"
    assert by_name["Never Heard Of This Case"]["status"] == "verified"
    assert by_name["Never Heard Of This Case"]["ik_url"] == "https://indiankanoon.org/doc/12345/"


def test_llm_clause_confidence_reflects_grounding_ratio(monkeypatch):
    # 2 statute refs (1 grounded) + 2 case law refs (1 verified) = 4 total, 2 grounded -> ratio 0.5
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate_json_factory(VALID_CLAUSE_JSON))
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "cause_of_action", db)
    # confidence = (grounding_ratio + model_confidence) / 2 = (0.5 + 0.8) / 2 = 0.65
    assert result["confidence"] == 0.65


def test_llm_clause_handles_malformed_json_without_crashing(monkeypatch):
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate_json_factory("not json at all"))
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    result = clause_generator.generate_clause(matter_id, outline_id, "facts", db)
    assert result["generation_warning"]
    assert result["content"]["text"] == ""
    assert result["statute_refs"] == []


def test_llm_clause_propagates_provider_error(monkeypatch):
    def _boom(*a, **k):
        raise ProviderError("all", "every provider failed")
    monkeypatch.setattr(clause_generator, "generate_json", _boom)
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    try:
        clause_generator.generate_clause(matter_id, outline_id, "prayer", db)
        assert False, "expected ProviderError to propagate"
    except ProviderError:
        pass


# --- Versioning ---------------------------------------------------------------

def test_regenerating_one_clause_never_touches_another():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    first_cause_title = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    parties_clause = clause_generator.generate_clause(matter_id, outline_id, "parties", db)
    second_cause_title = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)

    assert first_cause_title["version_no"] == 1
    assert second_cause_title["version_no"] == 2
    assert second_cause_title["regenerated"] is True
    assert first_cause_title["regenerated"] is False
    # parties clause row is completely untouched by the cause_title regeneration
    assert parties_clause["version_no"] == 1
    all_parties_versions = [r for r in db.store["litigation_pleading_clauses"] if r["clause_type"] == "parties"]
    assert len(all_parties_versions) == 1


def test_unknown_clause_type_rejected():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    try:
        clause_generator.generate_clause(matter_id, outline_id, "not_a_real_clause", db)
        assert False, "expected ClauseGeneratorError"
    except clause_generator.ClauseGeneratorError as exc:
        assert "unknown clause type" in str(exc).lower()


def test_generate_clause_requires_valid_outline():
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    try:
        clause_generator.generate_clause(matter_id, "nonexistent-outline", "cause_title", db)
        assert False, "expected ClauseGeneratorError"
    except clause_generator.ClauseGeneratorError as exc:
        assert "not found" in str(exc).lower()


def test_generate_all_clauses_produces_all_14_types_in_order(monkeypatch):
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate_json_factory(VALID_CLAUSE_JSON))
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    results = clause_generator.generate_all_clauses(matter_id, outline_id, db)
    assert [r["clause_type"] for r in results] == clause_generator.CLAUSE_TYPES
    assert len(clause_generator.CLAUSE_TYPES) == 14


# --- Review ---------------------------------------------------------------

def test_review_clause_approve_and_reject():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    clause = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    assert clause["review_status"] == "pending"

    approved = clause_generator.review_clause(clause["id"], matter_id, "approved", db)
    assert approved["review_status"] == "approved"
    assert approved["reviewed_at"] is not None


def test_review_clause_rejects_invalid_status():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    clause = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    try:
        clause_generator.review_clause(clause["id"], matter_id, "pending", db)
        assert False, "expected ClauseGeneratorError"
    except clause_generator.ClauseGeneratorError:
        pass
    try:
        clause_generator.review_clause(clause["id"], matter_id, "bogus", db)
        assert False, "expected ClauseGeneratorError"
    except clause_generator.ClauseGeneratorError:
        pass


def test_review_clause_requires_existing_clause():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    try:
        clause_generator.review_clause("nonexistent-id", matter_id, "approved", db)
        assert False, "expected ClauseGeneratorError"
    except clause_generator.ClauseGeneratorError:
        pass


def test_list_clauses_and_latest_clauses_by_type():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    clause_generator.generate_clause(matter_id, outline_id, "parties", db)

    all_clauses = clause_generator.list_clauses(matter_id, outline_id, db)
    assert len(all_clauses) == 3

    latest = clause_generator.latest_clauses_by_type(matter_id, outline_id, db)
    assert latest["cause_title"]["version_no"] == 2
    assert latest["parties"]["version_no"] == 1
