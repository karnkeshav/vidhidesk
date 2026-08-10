> **Title:** Database Architecture
> **Version:** 1.1
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents writing migrations
> **Last Updated:** 6 August 2026 (Sprint 3.5.5B — corrected a false "duplicate 0009 migration" claim; see the correction note in this file)
> **Canonical Reference:** Yes, for the current data model shape. The originally designed schema is in `90_Historical/Original_Technical_Requirements.md` §4 — this document extends it with what has actually been migrated since.
> **Supersedes:** `90_Historical/Original_Technical_Requirements.md` §4 (as the sole reference — kept as historical baseline, not current)
> **Related Documents:** [`../10_Architecture/Business_Architecture.md`](../10_Architecture/Business_Architecture.md), [`Repository_Standards.md`](Repository_Standards.md)

---

# Database Architecture

## Baseline model (originally designed, TRD §4)

```
users(id, email, ...)                      -- Supabase Auth
matters(id, user_id, title, client_name, module, created_at)
messages(id, matter_id, role, content, created_at)
citations(id, case_name, neutral_citation, ik_doc_id, ik_url, court, decided_on, verified_at, status)
templates(id, name, category, schema_json, docx_path, states_supported)
draft_versions(id, matter_id, template_id, version_no, docx_path, change_summary, created_at)
statute_chunks(id, act, section_no, year, text, embedding vector)
state_rules(id, state, instrument, stamp_duty, registration_req, notes, source_url, last_verified)
rera_guides(id, state, step_no, instruction, source_url, last_verified)
pii_masks(...)                              -- per-matter masking map, never sent to the LLM
```

## Confirmed additions since (per migration files and Build Tracker evidence)

| Migration | Adds |
|---|---|
| `0007_contracts_clause_review.sql` | `template_clauses`, `clause_reviews`, `draft_clause_fills`, plus `templates.template_key`, `templates.review_status` |
| `0008_generic_clause_conditions_and_numbering.sql` | `applicable_condition` JSONB, `heading` column — generalized clause inclusion logic |
| `0009_normalize_template_keys.sql` | Kebab-case normalization of all `template_key` values |
| `0010_add_template_id_to_matters.sql` | `matters.template_id` — enables clean matter-centric routing |
| `0011_create_advocate_profiles.sql` / `0012_simplify_advocate_profiles.sql` | `advocate_profiles` table, later simplified to `(id, user_id, full_name, designation, bar_number, primary_court, phone, office_address, avatar_url, created_at, updated_at)` |
| `0013_litigation_schema.sql` | `litigation_parties`, `litigation_facts_evidence`, `litigation_hearings`, plus additive columns on `matters` (`court_category`, `jurisdiction_state`, `cnr_number`, etc.) |
| `0014_litigation_case_analysis.sql` | `litigation_case_analyses` (versioned AI Case Analysis output), plus file-attachment columns on `litigation_facts_evidence` |

**Correction, 6 August 2026 (Sprint 3.5.5B):** this section previously claimed a `0009_litigation_pleadings_and_citations.sql` file existed, sharing a duplicate `0009_` prefix with `0009_normalize_template_keys.sql`, creating `litigation_pleadings`/`pleading_templates`/`case_citations` tables. **That file was never actually created.** The claim was sourced from `LITIGATION_ARCHITECTURE.md`'s originally *planned* migration (§3 of that document), never cross-checked against the real `api/migrations/` directory at the time this document was written. The litigation schema that actually shipped is `0013_litigation_schema.sql` / `0014_litigation_case_analysis.sql`, above — correctly, uniquely numbered, with a different (and real) table design. Verified by directly listing `api/migrations/` and, independently, by running `scripts/verify_migrations.py`'s live numbering check against the real files. See `docs/40_Validation/Technical_Debt_Report_2026-08-06.md` for the full correction record. **Lesson for future documentation work in this project: a planning document's stated intent is not evidence that the intent was carried out — cross-check against the actual repository, not just against another document.**

## Row-Level Security

Every table holding matter-scoped data is RLS-enabled, verified live via `scripts/verify_database.py`'s behavioral RLS checks (an unauthenticated anon-key client is confirmed to see 0 rows on every checkable table — see `40_Operations/Infrastructure_Verification.md`). The real policy shape for litigation tables (`0013_litigation_schema.sql`, `0014_litigation_case_analysis.sql`) is `EXISTS (SELECT 1 FROM matters m WHERE m.id = <table>.matter_id AND m.user_id = auth.uid())`, not a bare `matter_id IN (...)` subquery — apply the same `EXISTS`-against-parent-`matters` pattern to any new matter-scoped table, matching the existing convention in `0002_rls.sql` and `0007_contracts_clause_review.sql`.

## Migration discipline

All migrations are idempotent (safe to re-run) and run in strict numeric order via the Supabase SQL Editor — see [`../40_Operations/Local_Development_Setup.md`](../40_Operations/Local_Development_Setup.md) §4. Seed scripts follow the same idempotency convention (upsert by natural key).

For the full current schema, the migration files under `/api/migrations/` are the ground truth — this document is a navigational summary, not a substitute for reading them.
