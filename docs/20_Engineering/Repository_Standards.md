> **Title:** Repository Standards
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for repo layout and file/script conventions
> **Supersedes:** N/A
> **Related Documents:** [`Lessons_Learned.md`](Lessons_Learned.md), [`../40_Operations/Local_Development_Setup.md`](../40_Operations/Local_Development_Setup.md)

---

# Repository Standards

## Monorepo layout

```
/web        Next.js frontend
/api        FastAPI backend (app/, migrations/, scripts/, tests/)
/templates  Jinja2 .docx skeletons + JSON schemas, one pair per contract/pleading type
/corpus     Bare-act PDFs for statute ingestion
/docs       This documentation hierarchy
```

## Adding a template

A new template = adding schema + skeleton files, not new endpoint code — the intake form is auto-generated from the template's JSON schema. See [`../20_Engineering/API_Standards.md`](API_Standards.md) and [`Litigation_Module_Architecture.md`](../30_Implementation/Technical_Design/Litigation_Module_Architecture.md) §8 for the pipeline shape (skeleton → LLM fills bespoke clauses → assembled document).

## Seed scripts

One `seed_<template>_template.py` per template under `api/scripts/`, using the shared `api/scripts/template_seed_utils.py` pipeline (extracted in Build Tracker S3.5 specifically to eliminate duplicated seeding logic across templates). Seed scripts are idempotent (upsert by natural key) and must never silently overwrite a clause a human has already reviewed — see the `_write_clauses_preserving_review()` convention documented in [`Lessons_Learned.md`](Lessons_Learned.md) and `30_Implementation/Backlog.md`.

## Docx template authoring

Any new skeleton built with `api/scripts/build_nda_skeleton.py` (or its equivalents for other templates) as a reference must follow the `{{p ...}}` paragraph-tag convention for merged clause content and the `an_or_a` Jinja filter for grammatically correct articles — both are one-line fixes in the shared rendering engine that every future template inherits automatically. Full detail and failure symptoms in [`Lessons_Learned.md`](Lessons_Learned.md).

## Test data hygiene

Every matter created by a live E2E run must have its title prefixed `[TEST] ` so cleanup/audit queries can filter on `matters.title like '[TEST]%'` directly, rather than requiring a join through a specific throwaway auth account. Applies to `api/e2e/test_no_auto_pdf_download.py` and any ad hoc verification script.

## Exception: `docs/golden_tests.json`

This one file lives at the top level of `/docs` rather than in the reorganized hierarchy below it, because `api/tests/test_golden.py` reads it from a hardcoded path (`Path(__file__).resolve().parent.parent.parent / "docs" / "golden_tests.json"`). It is a test fixture, not documentation prose — treat it as part of the test suite's data, not as a candidate for future doc reorganization, unless the hardcoded path in `test_golden.py` is updated in the same change (which is application code, out of scope for a documentation-only refactor).
