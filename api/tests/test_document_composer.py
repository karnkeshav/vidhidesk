from __future__ import annotations

import json as _json

from app.services import clause_generator, document_composer
from app.services.llm_gateway import GenerationResult
from tests.test_clause_generator import DummyDBClient, _seed_full_matter, VALID_CLAUSE_JSON


def _fake_generate(prompt, task_type="chat", mask_map=None, entities=None, **kwargs):
    """Sprint 3.6 Phase 2A: generate_clause()'s LLM path now calls
    generate_json(), which returns (GenerationResult, parsed_dict) — not a
    bare GenerationResult. Kept the name `_fake_generate` (many existing
    call sites below reference it) even though it now fakes generate_json's
    contract, to minimize the diff."""
    result = GenerationResult(
        text=VALID_CLAUSE_JSON, provider="test", model="test-model", latency_ms=1, masked_prompt=prompt,
        requested_model="gemini-2.5-pro", degraded=False, fallback_chain=[],
    )
    return result, _json.loads(VALID_CLAUSE_JSON)


def _approve(db, matter_id, clause):
    return clause_generator.review_clause(clause["id"], matter_id, "approved", db)


def test_compose_pleading_reports_all_clauses_missing_when_none_generated():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    draft = document_composer.compose_pleading(matter_id, outline_id, db)
    assert draft["missing_clauses"] == clause_generator.CLAUSE_TYPES
    assert draft["composed_sections"] == []
    assert draft["version_no"] == 1


def test_compose_pleading_only_includes_approved_clauses(monkeypatch):
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate)
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    cause_title = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    _approve(db, matter_id, cause_title)
    # generated but never reviewed -> must not appear in the composed draft
    clause_generator.generate_clause(matter_id, outline_id, "parties", db)
    # generated and explicitly rejected -> must not appear
    facts = clause_generator.generate_clause(matter_id, outline_id, "facts", db)
    clause_generator.review_clause(facts["id"], matter_id, "rejected", db)

    draft = document_composer.compose_pleading(matter_id, outline_id, db)
    included_types = [s["clause_type"] for s in draft["composed_sections"]]
    assert included_types == ["cause_title"]
    assert "parties" in draft["missing_clauses"]
    assert "facts" in draft["missing_clauses"]
    assert len(draft["missing_clauses"]) == 13


def test_compose_pleading_preserves_fixed_order_and_numbering(monkeypatch):
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate)
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    # approve out of pipeline order
    for clause_type in ["prayer", "cause_title", "facts"]:
        clause = clause_generator.generate_clause(matter_id, outline_id, clause_type, db)
        _approve(db, matter_id, clause)

    draft = document_composer.compose_pleading(matter_id, outline_id, db)
    included_types = [s["clause_type"] for s in draft["composed_sections"]]
    # composer output follows CLAUSE_TYPES pipeline order, not approval order
    assert included_types == ["cause_title", "facts", "prayer"]
    paragraph_nos = [s["paragraph_no"] for s in draft["composed_sections"]]
    assert paragraph_nos == sorted(paragraph_nos)


def test_compose_pleading_uses_latest_approved_version_not_latest_overall(monkeypatch):
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate)
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    v1 = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    _approve(db, matter_id, v1)
    # regenerate — v2 exists but is never reviewed
    clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)

    draft = document_composer.compose_pleading(matter_id, outline_id, db)
    cause_title_section = next(s for s in draft["composed_sections"] if s["clause_type"] == "cause_title")
    used_version = draft["clause_versions"][0]["version_no"]
    assert used_version == 1  # v2 is unapproved, so v1 (approved) is still what's composed


def test_compose_pleading_traceability_records_clause_id_and_model():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    clause = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    _approve(db, matter_id, clause)

    draft = document_composer.compose_pleading(matter_id, outline_id, db)
    ref = draft["clause_versions"][0]
    assert ref["clause_id"] == clause["id"]
    assert ref["clause_type"] == "cause_title"
    assert ref["prompt_version"] == clause_generator.PROMPT_VERSION


def test_recomposing_after_approving_more_clauses_creates_new_version(monkeypatch):
    monkeypatch.setattr(clause_generator, "generate_json", _fake_generate)
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    cause_title = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    _approve(db, matter_id, cause_title)
    first_draft = document_composer.compose_pleading(matter_id, outline_id, db)
    assert first_draft["version_no"] == 1
    assert len(first_draft["composed_sections"]) == 1

    parties = clause_generator.generate_clause(matter_id, outline_id, "parties", db)
    _approve(db, matter_id, parties)
    second_draft = document_composer.compose_pleading(matter_id, outline_id, db)
    assert second_draft["version_no"] == 2
    assert len(second_draft["composed_sections"]) == 2
    # the first draft row itself is untouched — immutable, not updated in place
    drafts = document_composer.list_drafts(matter_id, outline_id, db)
    assert len(drafts) == 2
    assert drafts[0]["version_no"] == 2  # most recent first


def test_compose_pleading_requires_existing_outline():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    try:
        document_composer.compose_pleading(matter_id, "nonexistent-outline", db)
        assert False, "expected DocumentComposerError"
    except document_composer.DocumentComposerError:
        pass


def test_composer_never_calls_llm(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("document_composer must never call generate() — assembly only")
    monkeypatch.setattr("app.services.clause_generator.generate_json", _boom)
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    # compose with nothing approved — must not raise/crash and must not call generate()
    document_composer.compose_pleading(matter_id, outline_id, db)
