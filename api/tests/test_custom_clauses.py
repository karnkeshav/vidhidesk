"""Tests for advocate-authored custom clauses (clause_generator.py::
add_custom_clause, wired into document_composer.py's compose_pleading) --
the Litigation Pleading Workbench counterpart to Contracts' per-matter
clause customization. Confirms: a custom clause never touches the fixed
14 CLAUSE_TYPES pipeline, is auto-approved (advocate-authored, nothing to
review), and gets included in composed output after the fixed clauses."""

from __future__ import annotations

import pytest

from app.services import clause_generator, document_composer

from tests.test_clause_generator import DummyDBClient, _seed_full_matter


def test_add_custom_clause_creates_an_approved_human_authored_row():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    clause = clause_generator.add_custom_clause(
        matter_id, outline_id, "Limitation Point", "This suit is within limitation because...", db
    )

    assert clause["clause_type"] == "custom_limitation_point"
    assert clause["author"] == "human"
    assert clause["review_status"] == "approved"
    assert clause["is_deterministic"] is False
    assert clause["version_no"] == 1
    assert clause["content"]["text"] == "This suit is within limitation because..."
    assert clause["content"]["heading"] == "Limitation Point"


def test_add_custom_clause_requires_heading_and_text():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    with pytest.raises(clause_generator.ClauseGeneratorError):
        clause_generator.add_custom_clause(matter_id, outline_id, "", "text", db)
    with pytest.raises(clause_generator.ClauseGeneratorError):
        clause_generator.add_custom_clause(matter_id, outline_id, "Heading", "  ", db)


def test_add_custom_clause_rejects_a_non_custom_clause_type():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    with pytest.raises(clause_generator.ClauseGeneratorError):
        clause_generator.add_custom_clause(
            matter_id, outline_id, "Facts", "text", db, clause_type="facts"
        )


def test_revising_a_custom_clause_creates_a_new_version_of_the_same_type():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)
    v1 = clause_generator.add_custom_clause(matter_id, outline_id, "Limitation Point", "First draft.", db)
    v2 = clause_generator.add_custom_clause(
        matter_id, outline_id, "Limitation Point", "Revised draft.", db, clause_type=v1["clause_type"]
    )
    assert v2["clause_type"] == v1["clause_type"]
    assert v2["version_no"] == 2

    clauses = clause_generator.list_clauses(matter_id, outline_id, db)
    same_type = [c for c in clauses if c["clause_type"] == v1["clause_type"]]
    assert len(same_type) == 2


def test_custom_clause_appears_in_composed_pleading_after_fixed_clauses():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    cause_title = clause_generator.generate_clause(matter_id, outline_id, "cause_title", db)
    clause_generator.review_clause(cause_title["id"], matter_id, "approved", db)
    clause_generator.add_custom_clause(matter_id, outline_id, "Limitation Point", "Custom body.", db)

    draft = document_composer.compose_pleading(matter_id, outline_id, db)
    included_types = [s["clause_type"] for s in draft["composed_sections"]]
    assert included_types == ["cause_title", "custom_limitation_point"]

    custom_section = draft["composed_sections"][1]
    assert custom_section["heading"] == "Limitation Point"
    assert custom_section["text"] == "Custom body."
    # Never counted as a missing fixed clause.
    assert "custom_limitation_point" not in draft["missing_clauses"]
    assert len(draft["missing_clauses"]) == 13


def test_multiple_custom_clauses_ordered_by_creation():
    db = DummyDBClient()
    matter_id, ca_id, outline_id = _seed_full_matter(db)

    clause_generator.add_custom_clause(matter_id, outline_id, "First Point", "Body one.", db)
    clause_generator.add_custom_clause(matter_id, outline_id, "Second Point", "Body two.", db)

    draft = document_composer.compose_pleading(matter_id, outline_id, db)
    headings = [s["heading"] for s in draft["composed_sections"]]
    assert headings == ["First Point", "Second Point"]
