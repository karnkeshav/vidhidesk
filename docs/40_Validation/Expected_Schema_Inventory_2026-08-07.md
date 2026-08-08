> **Title:** Expected Schema Inventory — Deployment Recovery Sprint
> **Version:** 1.0
> **Status:** Active — planning artifact, not evidence of current production state (see `Gap_Analysis_2026-08-07.md` for that)
> **Owner:** Keshav
> **Audience:** Whoever executes the recovery (Nitesh or Keshav, via Supabase SQL Editor)
> **Last Updated:** 7 August 2026
> **Canonical Reference:** Yes, for what the schema *should* contain after all 14 migrations are applied — derived by reading every migration file in full, not by querying production
> **Related Documents:** [`README.md`](README.md), [`Migration_Execution_Checklist_2026-08-07.md`](Migration_Execution_Checklist_2026-08-07.md), [`Gap_Analysis_2026-08-07.md`](Gap_Analysis_2026-08-07.md), [`SQL_Verification_Checklist_2026-08-07.md`](SQL_Verification_Checklist_2026-08-07.md)

---

# Expected Schema Inventory

Every object below was extracted by reading `api/migrations/0001_schema.sql` through `0014_litigation_case_analysis.sql` in full — including `DROP` statements, so an object created in one migration and deliberately removed in a later one (there are three such cases, marked below) is listed in its *final* state, not double-counted as if it still existed. This is not a query against production — see `Gap_Analysis_2026-08-07.md` for what production actually contains as of this sprint.

## Tables (17)

| # | Table | Created by | Notes |
|---|---|---|---|
| 1 | `matters` | 0001 | |
| 2 | `messages` | 0001 | |
| 3 | `citations` | 0001 | |
| 4 | `templates` | 0001 | |
| 5 | `draft_versions` | 0001 | |
| 6 | `statute_chunks` | 0001 | |
| 7 | `state_rules` | 0001 | |
| 8 | `rera_guides` | 0001 | |
| 9 | `pii_masks` | 0001 | |
| 10 | `template_clauses` | 0007 | |
| 11 | `clause_reviews` | 0007 | |
| 12 | `draft_clause_fills` | 0007 | |
| 13 | `advocate_profiles` | 0011, columns reduced by 0012 | |
| 14 | `litigation_parties` | 0013 | |
| 15 | `litigation_facts_evidence` | 0013, columns added by 0014 | |
| 16 | `litigation_hearings` | 0013 | |
| 17 | `litigation_case_analyses` | 0014 | |

## Columns, per table (final state after all migrations)

**`matters`** (0001, extended by 0010, 0013): `id` uuid PK, `user_id` uuid FK→`auth.users`, `title` text, `client_name` text, `module` text CHECK, `created_at` timestamptz, `template_id` uuid FK→`templates` (0010), `court_category` text, `jurisdiction_state` text, `cnr_number` text, `case_number_formatted` text, `litigation_stage` text, `court_name` text, `bench_name` text (all six from 0013).

**`messages`** (0001): `id`, `matter_id` FK→`matters`, `role` text CHECK, `content` text, `model_used` text, `masked_prompt` text, `retrieval_sources` jsonb, `created_at`.

**`citations`** (0001, extended by 0003/0005): `id`, `case_name` text, `neutral_citation` text, `ik_doc_id` text, `ik_url` text, `court` text, `decided_on` date, `status` text CHECK, `verified_at` timestamptz, `created_at`, `case_name_normalized` text (app-populated, not a generated column since 0005), `stale` boolean (0003), `last_checked_at` timestamptz (0003).

**`templates`** (0001, extended by 0007): `id`, `name`, `category`, `schema_json` jsonb, `docx_path`, `states_supported` text[], `created_at`, `review_status` text CHECK (0007), `template_key` text (0007).

**`draft_versions`** (0001): `id`, `matter_id` FK, `template_id` FK→`templates` (nullable), `version_no` int, `docx_path`, `change_summary`, `created_at`.

**`statute_chunks`** (0001, extended by 0006): `id`, `act` text, `section_no` text, `year` int, `text` text, `embedding` vector(384), `created_at`, `text_search` tsvector GENERATED (0006).

**`state_rules`** (0001): `id`, `state`, `instrument`, `stamp_duty`, `registration_req`, `notes`, `source_url`, `last_verified`.

**`rera_guides`** (0001): `id`, `state`, `step_no` int, `instruction`, `source_url`, `last_verified`.

**`pii_masks`** (0001): `id`, `matter_id` FK, `placeholder`, `real_value`, `kind`, `created_at`.

**`template_clauses`** (0007, modified by 0008): `id`, `template_id` FK→`templates`, `clause_key`, `display_order` int, `clause_type` text CHECK, `source_text`, `current_text`, `review_status` text CHECK, `reviewed_at`, `created_at`, `applicable_condition` jsonb (0008, replaces the original `applicable_variant` column which 0008 drops), `heading` text (0008).

**`clause_reviews`** (0007): `id`, `clause_id` FK→`template_clauses`, `decision` text CHECK, `redraft_text`, `reviewer_notes`, `created_at`.

**`draft_clause_fills`** (0007): `id`, `draft_version_id` FK→`draft_versions`, `template_clause_id` FK→`template_clauses`, `generated_text`, `prompt`, `model_used`, `retrieval_sources_json` jsonb, `created_at`.

**`advocate_profiles`** (0011, reduced by 0012): `id`, `user_id` uuid UNIQUE FK→`auth.users`, `full_name`, `designation` text default `'Advocate'`, `bar_number`, `primary_court`, `phone` text CHECK (E.164-ish regex), `office_address`, `avatar_url`, `created_at`, `updated_at`. **Columns 0011 created and 0012 deliberately dropped (must NOT exist in a correct final state):** `enrollment_state`, `enrollment_year`, `high_court_roll_no`, `aor_code`, `firm_name`, `practice_areas`, `states_of_practice`, `languages_spoken`, `rera_advocate_reg_no`.

**`litigation_parties`** (0013): `id`, `matter_id` FK→`matters` CASCADE, `party_type` text, `party_name` text, `party_number` int default 1, `address`, `advocate_name`, `created_at`.

**`litigation_facts_evidence`** (0013, extended by 0014): `id`, `matter_id` FK CASCADE, `event_date` date, `fact_summary` text, `exhibit_number`, `document_title`, `relevance_notes`, `created_at`, `file_url` text (0014), `file_name` text (0014), `file_size_bytes` bigint (0014), `mime_type` text (0014).

**`litigation_hearings`** (0013): `id`, `matter_id` FK CASCADE, `hearing_date` date, `cause_list_item_no` int, `purpose_of_hearing`, `ia_number`, `hearing_outcome`, `next_hearing_date` date, `status` text default `'Scheduled'`, `created_at`.

**`litigation_case_analyses`** (0014): `id`, `matter_id` FK CASCADE, `version_no` int, `chronological_facts` jsonb, `jurisdiction_summary` jsonb, `limitation_summary` jsonb, `applicable_statutes` jsonb, `matter_summary` text, `missing_information` jsonb, `possible_causes_of_action` jsonb, `potential_risks` jsonb, `evidence_gaps` jsonb, `recommended_next_steps` jsonb, `possible_precedents` jsonb, `model_used` text, `masked_prompt` text, `retrieval_sources` jsonb, `generation_warning` text, `created_at`.

## Indexes (17, net of deliberate drops)

| Index | Table | Created by | Notes |
|---|---|---|---|
| `matters_user_id_idx` | `matters` | 0001 | |
| `messages_matter_id_idx` | `messages` | 0001 | |
| `pii_masks_matter_id_idx` | `pii_masks` | 0001 | |
| `statute_chunks_act_section_uq` | `statute_chunks` | 0003 | unique(act, section_no) |
| `statute_chunks_embedding_hnsw_idx` | `statute_chunks` | 0003 | HNSW, vector_cosine_ops |
| `statute_chunks_act_trgm_idx` | `statute_chunks` | 0003 | GIN, pg_trgm |
| `citations_normalized_uq` | `citations` | 0005 | unique(case_name_normalized, coalesce(neutral_citation,'')) — **replaces** `citations_case_court_uq`, which 0001 created and 0005 explicitly drops. `citations_case_court_uq` must **NOT** exist in a correct final state. |
| `statute_chunks_text_search_idx` | `statute_chunks` | 0006 | GIN on `text_search` |
| `templates_template_key_uq` | `templates` | 0007 | unique, partial (`where template_key is not null`) |
| `template_clauses_template_id_idx` | `template_clauses` | 0007 | |
| `clause_reviews_clause_id_idx` | `clause_reviews` | 0007 | |
| `draft_clause_fills_draft_version_id_idx` | `draft_clause_fills` | 0007 | |
| `idx_advocate_profiles_user_id` | `advocate_profiles` | 0011 | unique |
| `idx_litigation_parties_matter` | `litigation_parties` | 0013 | |
| `idx_litigation_facts_matter` | `litigation_facts_evidence` | 0013 | on (matter_id, event_date) |
| `idx_litigation_hearings_matter` | `litigation_hearings` | 0013 | on (matter_id, hearing_date) |
| `idx_litigation_case_analyses_matter` | `litigation_case_analyses` | 0014 | on (matter_id, version_no desc) |

**Indexes 0011 created and 0012 deliberately dropped (must NOT exist):** `idx_advocate_profiles_bar_state`, `idx_advocate_profiles_enrollment_state`.

Plus unnamed unique constraints that Postgres backs with an implicit index: `draft_versions(matter_id, version_no)`, `pii_masks(matter_id, placeholder)`, `template_clauses(template_id, clause_key)`, `litigation_case_analyses(matter_id, version_no)`, `advocate_profiles(user_id)` (already listed above as `idx_advocate_profiles_user_id`, explicitly named).

## Constraints (non-index)

| Table | Constraint | Type |
|---|---|---|
| `matters` | `module in ('litigation','contracts','rera','consulting')` | CHECK |
| `messages` | `role in ('user','assistant','system')` | CHECK |
| `citations` | `status in ('verified','unverified')` | CHECK |
| `citations` | `citations_verified_has_doc_id`: `status='unverified' or ik_doc_id is not null` | CHECK, named |
| `draft_versions` | `unique(matter_id, version_no)` | UNIQUE |
| `pii_masks` | `unique(matter_id, placeholder)` | UNIQUE |
| `template_clauses` | `clause_type in ('fixed_boilerplate','llm_fillable')` | CHECK |
| `template_clauses` | `review_status in ('unreviewed','kept','redrafted','deleted')` | CHECK |
| `template_clauses` | `unique(template_id, clause_key)` | UNIQUE |
| `clause_reviews` | `decision in ('keep','redraft','delete')` | CHECK |
| `clause_reviews` | `clause_reviews_redraft_has_text`: `decision <> 'redraft' or redraft_text is not null` | CHECK, named |
| `clause_reviews` | `clause_reviews_delete_has_notes`: `decision <> 'delete' or reviewer_notes is not null` | CHECK, named |
| `advocate_profiles` | `user_id` UNIQUE | UNIQUE |
| `advocate_profiles` | `phone is null or phone ~ '^\+?[1-9]\d{1,14}$'` | CHECK |
| `litigation_case_analyses` | `unique(matter_id, version_no)` | UNIQUE |
| every table with a `matter_id`/`user_id`/`template_id`/`clause_id`/`draft_version_id`/`template_clause_id` column | FK to the referenced table, `ON DELETE CASCADE` where the migration specifies it | FOREIGN KEY |

**Constraint 0011 created and 0012 dropped (must NOT exist):** `uq_advocate_profiles_bar_state` (`unique(bar_number, enrollment_state)`) — dropped because its underlying `enrollment_state` column was dropped.

## RLS policies (35 total across 16 RLS-enabled tables)

`pii_masks` is RLS-**enabled** but deliberately carries **zero** policies for any non-service role (0002's own comment: the masking map is only ever touched via the service-role key, which bypasses RLS — no policy at all is the correct, intentional final state for this one table).

| Table | Policies | Created by |
|---|---|---|
| `matters` | `matters_owner_all` (ALL, owner-only) | 0002 |
| `messages` | `messages_owner_all` (ALL, via parent `matters`) | 0002 |
| `draft_versions` | `draft_versions_owner_all` (ALL, via parent `matters`) | 0002 |
| `pii_masks` | *(none — intentional)* | 0002 |
| `citations` | `citations_read_authenticated` (SELECT) | 0002 |
| `templates` | `templates_read_authenticated` (SELECT) | 0002 |
| `statute_chunks` | `statute_chunks_read_authenticated` (SELECT) | 0002 |
| `state_rules` | `state_rules_read_authenticated` (SELECT) | 0002 |
| `rera_guides` | `rera_guides_read_authenticated` (SELECT) | 0002 |
| `template_clauses` | `template_clauses_read_authenticated` (SELECT) | 0007 |
| `clause_reviews` | `clause_reviews_read_authenticated` (SELECT) | 0007 |
| `draft_clause_fills` | `draft_clause_fills_owner_all` (ALL, via `draft_versions`→`matters`) | 0007 |
| `advocate_profiles` | `advocate_profiles_select_owner`, `_insert_owner`, `_update_owner`, `_delete_owner` (4) | 0011 |
| `litigation_parties` | `litigation_parties_select_owner`, `_insert_owner`, `_update_owner`, `_delete_owner` (4) | 0013 |
| `litigation_facts_evidence` | `litigation_facts_select_owner`, `_insert_owner`, `_update_owner`, `_delete_owner` (4) | 0013 |
| `litigation_hearings` | `litigation_hearings_select_owner`, `_insert_owner`, `_update_owner`, `_delete_owner` (4) | 0013 |
| `litigation_case_analyses` | `litigation_case_analyses_select_owner`, `_insert_owner` (2 — no update/delete: analysis versions are immutable by design) | 0014 |

## RPCs (2)

| RPC | Signature | Created by | Access |
|---|---|---|---|
| `match_statute_chunks` | `(query_embedding vector(384), match_count int default 5)` | 0004 | `EXECUTE` granted to `authenticated`, `service_role`. Explicitly **revoked** from `public` and `anon` — both revokes are required per 0004's own documented finding that Supabase auto-grants `anon` execute twice, through two different mechanisms. |
| `search_statute_chunks_fulltext` | `(query_text text, match_count int default 5)` | 0006 | Same access pattern as above. |

## Views (0)

**None.** Confirmed by searching every migration for `CREATE [OR REPLACE] VIEW` with a word-boundary-safe pattern — zero matches. (An earlier, looser check produced a false positive matching "clause_**review**s" as if it contained "view"; corrected before this inventory was finalized.) If a verification step ever reports a view "missing," that's a sign the check itself is wrong, not the schema.

## Storage buckets (2)

| Bucket | Referenced by | Access model implied by existing code |
|---|---|---|
| `avatars` | `api/app/routers/profile.py::upload_avatar` | Public (`get_public_url()` is called on the uploaded path) |
| `evidence` | `api/app/routers/litigation.py::upload_evidence` | Public (`get_public_url()` is called the same way) — **flagged as a decision point in `Production_Recovery_Plan_2026-08-07.md`**: evidence documents are client-confidential, and a public bucket makes any uploaded file accessible to anyone with the URL, not just the owning advocate. This matches what the *existing, already-shipped* code assumes, but is worth a deliberate yes/no from whoever runs the recovery, not a silent default. |

**Important, and easy to miss:** neither bucket is created by any SQL migration. Storage buckets are Supabase Storage objects, not schema DDL — none of the 14 files in `api/migrations/` contain bucket-creation SQL. Provisioning them is a separate action from "run the migrations," addressed on its own in the recovery plan.
