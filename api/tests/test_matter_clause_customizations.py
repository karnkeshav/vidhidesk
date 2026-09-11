"""Tests for per-matter clause customization (app/services/contracts.py's
list_matter_clause_customizations/upsert_matter_clause_decision/
add_custom_matter_clause/delete_matter_clause_customization, wired into
generate_draft() -- see 0031_matter_clause_customizations.sql).

Every lawyer's own keep/modify/delete/custom decisions for THEIR matter,
layered on top of the shared template_clauses baseline -- never written
back to template_clauses, never visible to any other matter. These tests
confirm both the CRUD functions and that generate_draft() actually
applies the decisions when assembling a draft."""

from __future__ import annotations

import pytest

from app.services import contracts

from tests.test_contracts import (
    BASE_FORM,
    REPO_ROOT,
    FakeDB,
    _fake_generate,
    _seed_matter,
    _seed_template,
)


def test_upsert_decision_rejects_invalid_decision():
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    with pytest.raises(ValueError):
        contracts.upsert_matter_clause_decision(
            matter_id, "clause-definitions", "custom", None, db
        )


def test_upsert_decision_modified_requires_custom_text():
    db = FakeDB()
    _seed_template(db)
    matter_id = _seed_matter(db)
    with pytest.raises(ValueError):
        contracts.upsert_matter_clause_decision(
            matter_id, "clause-definitions", "modified", "  ", db
        )


def test_upsert_decision_rejects_unknown_template_clause():
    db = FakeDB()
    _seed_template(db)
    matter_id = _seed_matter(db)
    with pytest.raises(ValueError):
        contracts.upsert_matter_clause_decision(
            matter_id, "does-not-exist", "deleted", None, db
        )


def test_upsert_decision_re_deciding_updates_same_row_not_a_second_one():
    db = FakeDB()
    _seed_template(db)
    matter_id = _seed_matter(db)
    first = contracts.upsert_matter_clause_decision(
        matter_id, "clause-definitions", "deleted", None, db
    )
    second = contracts.upsert_matter_clause_decision(
        matter_id, "clause-definitions", "modified", "New text", db
    )
    assert first["id"] == second["id"]
    rows = contracts.list_matter_clause_customizations(matter_id, db)
    assert len(rows) == 1
    assert rows[0]["decision"] == "modified"
    assert rows[0]["custom_text"] == "New text"


def test_add_custom_clause_and_list():
    db = FakeDB()
    _seed_template(db)
    matter_id = _seed_matter(db)
    row = contracts.add_custom_matter_clause(matter_id, "Non-Compete", "Clause body here.", db)
    assert row["decision"] == "custom"
    assert row["template_clause_id"] is None
    assert row["heading"] == "Non-Compete"
    assert row["display_order"] == 0

    second = contracts.add_custom_matter_clause(matter_id, "Force Majeure", "Body two.", db)
    assert second["display_order"] == 1

    rows = contracts.list_matter_clause_customizations(matter_id, db)
    assert len(rows) == 2


def test_add_custom_clause_requires_heading_and_text():
    db = FakeDB()
    _seed_template(db)
    matter_id = _seed_matter(db)
    with pytest.raises(ValueError):
        contracts.add_custom_matter_clause(matter_id, "", "Body", db)
    with pytest.raises(ValueError):
        contracts.add_custom_matter_clause(matter_id, "Heading", "  ", db)


def test_delete_customization_reverts_a_template_override():
    db = FakeDB()
    _seed_template(db)
    matter_id = _seed_matter(db)
    row = contracts.upsert_matter_clause_decision(
        matter_id, "clause-definitions", "deleted", None, db
    )
    contracts.delete_matter_clause_customization(matter_id, row["id"], db)
    assert contracts.list_matter_clause_customizations(matter_id, db) == []


# --- generate_draft() actually applies these decisions ----------------------


def test_generate_draft_omits_a_deleted_clause(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    contracts.upsert_matter_clause_decision(matter_id, "clause-definitions", "deleted", None, db)

    result = contracts.generate_draft(matter_id, template_id, dict(BASE_FORM), db=db)
    assert "Definitions" not in result.full_text
    assert "Fixed boilerplate text." not in result.full_text


def test_generate_draft_uses_modified_text_verbatim_not_the_template_clause(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    contracts.upsert_matter_clause_decision(
        matter_id, "clause-definitions", "modified", "This matter's own custom definitions text.", db
    )

    result = contracts.generate_draft(matter_id, template_id, dict(BASE_FORM), db=db)
    assert "This matter's own custom definitions text." in result.full_text
    assert "Fixed boilerplate text." not in result.full_text


def test_generate_draft_appends_custom_clauses_after_template_clauses(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    contracts.add_custom_matter_clause(matter_id, "Non-Compete", "Neither party shall compete.", db)

    result = contracts.generate_draft(matter_id, template_id, dict(BASE_FORM), db=db)
    assert "Non-Compete" in result.full_text
    assert "Neither party shall compete." in result.full_text
    # Appended after the template's own clauses, not interleaved.
    assert result.full_text.index("Non-Compete") > result.full_text.index("Fixed boilerplate text.")


def test_generate_draft_with_no_customizations_is_unaffected(monkeypatch):
    """A matter with zero rows in matter_clause_customizations must render
    identically to before this feature existed -- the whole point of this
    being strictly additive per-matter data."""
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result = contracts.generate_draft(matter_id, template_id, dict(BASE_FORM), db=db)
    assert "Fixed boilerplate text." in result.full_text


def test_generate_draft_real_docx_includes_custom_clause_and_still_renders_everything_else(monkeypatch):
    """End-to-end against the real templates/contracts/nda.docx skeleton
    (same pattern as test_contracts.py's own
    test_generate_draft_renders_real_docx_skeleton) -- confirms a matter's
    custom clause and modified-clause override survive into the actual
    rendered .docx file (and therefore the PDF export, which converts
    this exact file -- see app/routers/contracts.py::download_draft_pdf),
    and that everything that worked before this feature still does."""
    from docx import Document

    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db, matter_id="matter-custom-clause-docx-test")
    _fake_generate(monkeypatch, canned_text="WHEREAS the parties wish to collaborate.")

    contracts.upsert_matter_clause_decision(
        matter_id, "clause-definitions", "modified", "This matter's own custom definitions text.", db
    )
    contracts.add_custom_matter_clause(matter_id, "Non-Compete", "Neither party shall compete.", db)

    result = contracts.generate_draft(matter_id, template_id, dict(BASE_FORM), db=db)
    output_path = REPO_ROOT / result.docx_path
    try:
        assert output_path.exists()
        doc = Document(str(output_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        # Everything that worked before this feature still works.
        assert "Ramesh Kumar" in full_text
        assert "WHEREAS the parties wish to collaborate." in full_text
        # The modified override replaced the template's own clause text.
        assert "This matter's own custom definitions text." in full_text
        assert "Fixed boilerplate text." not in full_text
        # The custom clause was appended, with its own heading and number.
        assert "Non-Compete" in full_text
        assert "Neither party shall compete." in full_text
    finally:
        output_path.unlink(missing_ok=True)
