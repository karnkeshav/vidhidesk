> **Title:** Implementation Backlog (deferred tickets)
> **Version:** Living document
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Engineers planning upcoming sprints
> **Last Updated:** 9 August 2026 (Sprint 3.6 Phase 2A — TICKET-25 substantially resolved, TICKET-26 partial note)
> **Canonical Reference:** Yes, for deferred/open engineering tickets
> **Supersedes:** N/A
> **Related Documents:** [`30_Implementation/Build_Tracker.md`](Build_Tracker.md), [`20_Engineering/Lessons_Learned.md`](../20_Engineering/Lessons_Learned.md)

---

# Sprint 3 Backlog

Tickets accumulated during Sprint 1 (Statute RAG + Citation Verifier)
and Sprint 2 (Contracts template engine, Batches 1-3) that were
deliberately deferred rather than fixed in-flight — captured here so
Sprint 3 kickoff starts from an honest list, not a rediscovery of gaps.
Each entry names where it was surfaced; see that source for full context
before starting the work.

## Litigation — Production Provisioning (found Sprint 3.5.5A, real infrastructure validation)

**~~TICKET-9: Litigation migrations never applied to the real Supabase
project.~~ — CLOSED 8 August 2026, Sprint D1.** Both migrations applied
via `supabase db query --linked`; every table/column/index/RLS policy
re-confirmed present by direct SQL query against the live catalog. See
Build_Tracker.md E35.
Classification: **Critical** — complete blocker, not a code defect. Real,
authenticated connectivity to the production Supabase project
(`pgwemjswxdlnshrfoggj`) confirms `litigation_parties`,
`litigation_facts_evidence`, `litigation_hearings`, and
`litigation_case_analyses` do not exist — every query returns
`PGRST205: Could not find the table 'public.<name>' in the schema
cache`, independently re-confirmed via a direct PostgREST OpenAPI schema
fetch (13 total tables exposed, zero containing "litigation"). Migrations
`0013_litigation_schema.sql` and `0014_litigation_case_analysis.sql` —
both already written, reviewed, and merged in Sprint 3.5.3 — have simply
never been run against this project. Since the Litigation Parties step is
a precondition for every downstream step (Facts, Evidence, AI Case
Analysis all require `litigation_parties`/`litigation_facts_evidence` to
exist, and `case_analysis.py`'s own precondition check requires at least
one party on record), this alone makes the entire documented Litigation
workflow (Matter → Parties → Facts → Evidence → ... → AI Case Analysis)
unexecutable against production, for every scenario, regardless of LLM
provider health. Fix: run both migrations via the Supabase SQL Editor per
`40_Operations/Local_Development_Setup.md` §4. Both are idempotent and
additive (`IF NOT EXISTS` throughout) — low risk to the 71 existing
Contracts-module `matters` rows already in this database, but this is a
real production database and the migration should be applied
deliberately by someone who can confirm it, not silently mid-validation.
*Source: `docs/40_Validation/Runtime_Validation_Report_2026-08-06.md`
(Sprint 3.5.5A), 6 August 2026 — found via real, authenticated Supabase
queries against the live project, not inferred from code reading.*

**~~TICKET-10: No Supabase Storage buckets provisioned.~~ — CLOSED
8 August 2026, Sprint D1.** Both `evidence` and `avatars` buckets
created (`evidence` as public, per the user-approved Option A — see
TICKET-13 for the tracked follow-up to private/signed-URL); real
upload/download round-trip verified against both. See Build_Tracker.md
E35.
Classification: **Major** — blocks genuine exercise of Evidence Upload,
degrades gracefully rather than hard-blocking. `service_client()
.storage.list_buckets()` returns an empty list against the real project —
zero buckets exist. Both `evidence` (`api/app/routers/litigation.py
::upload_evidence`) and `avatars` (`api/app/routers/profile.py
::upload_avatar`) reference buckets that were never created. Both
endpoints already have a non-fatal fallback (log a warning, continue
without a `file_url`/`avatar_url` rather than raise), so this does not
crash the application — but it means the evidence-upload feature cannot
be genuinely exercised end-to-end in production right now, only its
failure-path. Fix: create both buckets in the Supabase dashboard (Storage
→ New bucket), with appropriate public/private access policy matching
what `upload_avatar`'s `get_public_url()` call assumes for `avatars`, and
equivalent for `evidence`.
*Source: `docs/40_Validation/Runtime_Validation_Report_2026-08-06.md`
(Sprint 3.5.5A), 6 August 2026.*

**TICKET-11: `CEREBRAS_API_KEY` is invalid.**
Classification: **Minor** — no practical impact today. A real, direct
call to the Cerebras API with the configured key returns
`HTTP 401: {"message":"Wrong API Key", ...}`. Cerebras is the fourth and
last tier in the LLM Gateway's failover chain
(`CLAUDE.md` Decision 3); Gemini, Groq, and SambaNova were all confirmed
working in the same test run, so in practice every request succeeds
before the chain ever reaches Cerebras. Still worth fixing so the fourth
tier is a real safety net rather than a guaranteed-fail no-op if the
first three providers ever have a simultaneous outage.
*Source: `docs/40_Validation/Runtime_Validation_Report_2026-08-06.md`
(Sprint 3.5.5A), 6 August 2026.*

## Storage — evidence bucket confidentiality (found Deployment Recovery Sprint D1)

**TICKET-13: `evidence` bucket is public — migrate to private with signed
URLs before production release.** Classification: **Major** (security /
confidentiality posture, not a functional bug — the feature works
correctly today, just with a weaker access-control guarantee than client
evidence documents warrant). Created as `public: true`
(`Production_Recovery_Plan_2026-08-07.md` Step 4, approved 8 August 2026)
specifically because the already-shipped `upload_evidence` endpoint
(`api/app/routers/litigation.py`) calls `get_public_url()`, which only
resolves to something fetchable if the bucket is public — making it
private today, without a corresponding code change, would leave upload
"succeeding" while every returned `file_url` 403s when opened, a
silently broken feature. That code change was explicitly out of scope
for a deployment-synchronization sprint ("no feature development, no
refactoring").

**What "migrate to private" actually requires** (scope for whichever
future sprint picks this up):
1. Create a new **private** bucket (or flip `evidence.public` to `false`
   once no `file_url` values depend on the public form — see the
   backfill note below).
2. `api/app/routers/litigation.py::upload_evidence` — replace
   `svc.storage.from_("evidence").get_public_url(storage_path)` with
   `svc.storage.from_("evidence").create_signed_url(storage_path,
   expires_in=...)`.
3. `api/app/services/litigation.py::list_evidence` (or the router layer
   above it) — a stored signed URL goes stale after its expiry, so the
   **list** path needs to regenerate a fresh signed URL per request
   rather than returning whatever was persisted at upload time. This is
   the part most likely to be underestimated — it's not a one-line swap
   at the upload endpoint alone.
4. Decide what happens to `file_url` values already stored under the
   public-bucket regime (this sprint's approved choice) before this
   ticket is picked up — those rows currently hold permanent public
   URLs; migrating the bucket to private without addressing them would
   break every existing evidence link retroactively, not just future
   ones.
5. Corresponding frontend change: `web/src/components/litigation-fact-timeline.tsx`
   currently renders `fact.file_url` as a static `<a href>` — fine for a
   signed URL string too, but only if step 3 is guaranteeing freshness
   on every list render; a stale link rendered from a cached page load
   would silently 403.

*Source: `Production_Recovery_Plan_2026-08-07.md`'s explicit Option
A/Option B analysis, presented to and decided by the user 8 August
2026 — Option A approved for this sprint's scope, with this ticket
filed immediately per that approval as the tracked path to Option B.*

## Migrations — RLS policy idempotency (found Sprint 3.5.5B)

**TICKET-12: `0011`, `0013`, `0014` use bare `CREATE POLICY` without a
preceding `DROP POLICY IF EXISTS`, unlike the project's own established
pattern.** Classification: **Major** (per `40_Validation/Technical_Debt_Report_2026-08-06.md`'s
scheme). `0002_rls.sql` and `0007_contracts_clause_review.sql` both
correctly use `drop policy if exists <name> on <table>; create policy
<name> ...` so a re-run doesn't error on an already-existing policy.
`0011_create_advocate_profiles.sql`'s four policies
(`advocate_profiles_select_owner`, `_insert_owner`, `_update_owner`,
`_delete_owner`), `0013_litigation_schema.sql`'s twelve policies (four
each on `litigation_parties`, `litigation_facts_evidence`,
`litigation_hearings`), and `0014_litigation_case_analysis.sql`'s two
policies (`litigation_case_analyses_select_owner`, `_insert_owner`) all
skip the guard. This does not block a first-time apply (TICKET-9 is
still the immediate blocker for those two files) — it only surfaces if
any of the three is genuinely re-run against a database where it already
applied, which would then fail with a "policy already exists" error
rather than completing idempotently as every other migration in this
project promises to. Fix: add the missing `drop policy if exists`
lines, matching the `0002`/`0007` pattern, for every policy in all three
files.
*Source: `api/scripts/verify_migrations.py` (new in this sprint), run for
real against the repository, 6 August 2026 —
`docs/40_Validation/Technical_Debt_Report_2026-08-06.md` T-1.*

## Litigation — Limitation Engine

**~~TICKET-5: Off-by-one-day error in Article 115/116 limitation
computation.~~ — SHIPPED 6 August 2026, fixed same day it was found.**
`api/app/services/limitation.py`'s `LIMITATION_ARTICLES["Appeal"]` encoded
Article 116 (90-day HC appeal) as `"statutory_period_years": 0.2465` and
Article 115 (30-day District/Subordinate Court appeal) as `0.0821`, both
converted to a day count via `int(years * 365)` in
`calculate_limitation()`. `int(0.2465 * 365)` = `int(89.9725)` = **89**,
not 90; `int(0.0821 * 365)` = `int(29.9665)` = **29**, not 30 — both
truncated one day short of the correct statutory period, confirmed by
directly running `calculate_limitation()` against known dates (a
2026-06-20 decree computed an Article 116 expiry of 2026-09-17, one day
before the legally correct 2026-09-18). Fixed by changing the truncating
`int()` to `round()` in the day-based branch of `calculate_limitation()`
— `round(89.9725) == 90`, `round(29.9665) == 30`, correctly recovering the
intended whole-day count from the stored year-fraction. Re-verified
against the same dates post-fix (2026-09-18/43 days remaining;
2026-08-19/13 days remaining for the Article 115 case). Locked in by
`test_limitation_appeal_article_116_ninety_days_exact` and
`test_limitation_appeal_article_115_thirty_days_exact` in
`api/tests/test_limitation.py`.
*Source: `docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`
scenarios APP-01/APP-02/APP-03, found 6 August 2026 while authoring the
guide (direct execution against the live code, not a hypothetical);
fixed the same day at the user's explicit request, before the first
human validation round.*

**~~TICKET-6: Forum Advisor recommends the general civil court over the
Commercial Court for qualifying Commercial Disputes.~~ — SHIPPED
6 August 2026, fixed same day it was found.**
`api/app/services/forum.py::determine_forum()` appended a Commercial Court
option to `viable_options` first when `suit_type == "Commercial Dispute"
and claim_value_inr >= 3_00_000`, but then unconditionally
`viable_options.insert(0, civil_option)` for any suit type other than
RERA/Real Estate — pushing the just-added Commercial Court option to
index 1 and making `recommended_forum = viable_options[0]` return the
general civil court instead, even though Commercial Court designation is
frequently the legally apt (and sometimes exclusive) answer above the
Commercial Courts Act, 2015 threshold. Confirmed via direct execution
against three states (Delhi, Maharashtra, Karnataka) — reproduced
identically in all three. Fixed by introducing a `commercial_court_added`
flag and extending the same append-after-rather-than-insert-before
condition the RERA branch already used correctly
(`suit_type in ("RERA", "Real Estate")`) to also cover
`commercial_court_added` — so a qualifying Commercial Court option now
stays at index 0 / recommended, the same way the RERA tribunal already
did. Re-verified against the same three states post-fix, plus two
non-regression checks (RERA ordering unchanged; a Commercial Dispute
*below* the ₹3,00,000 threshold still correctly recommends the general
civil court, since no Commercial Court option exists to prioritize in
that case). Locked in by
`test_forum_commercial_courts_act_recommends_commercial_court_not_general_civil`
and `test_forum_commercial_dispute_below_threshold_recommends_general_civil`
in `api/tests/test_forum.py`.
*Source: `docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`
scenarios COM-01/COM-02/COM-03/IA-03, found 6 August 2026 during the same
authoring-time verification as TICKET-5; fixed the same day.*

## AI Case Analysis — PII masking (found & fixed Deployment Recovery Sprint D1)

**~~TICKET-14: AI Case Analysis returned HTTP 500 on every real call —
`pii_masks` insert rejected by RLS.~~ — SHIPPED 8 August 2026, fixed
same day it was found.** First-ever live exercise of
`POST /api/matters/{id}/case-analysis` against production (Sprint D1
smoke test) failed with `postgrest.exceptions.APIError: new row
violates row-level security policy for table "pii_masks"` (code
`42501`), after ~61s (the request itself succeeded through the LLM
failover chain — a logged Gemini rate-limit was a red herring, Groq/
SambaNova picked it up — the crash was purely on the DB write after
generation). `pii_masks` deliberately carries **no** RLS policies at
all (`migrations/0002_rls.sql`: "no direct client access at all... only
the backend using the service-role key, which bypasses RLS"). But
`api/app/routers/litigation.py::generate_case_analysis` calls
`case_analysis.generate_case_analysis(..., db=user.db)` — the
RLS-scoped, per-request-user client — and `case_analysis.py` reused
that same `db` to construct `SupabaseMaskStore(db)`, so every
`pii_masks` read/write ran as the authenticated user, which the table
is designed to always reject. This was never caught by unit tests
because they exercise `case_analysis.py` against a `DummyDBClient` mock
that doesn't enforce RLS — only a real integration/smoke test against
live Postgres could surface it, which is exactly what Sprint D1's
smoke test was for. The rest of the codebase already gets this right
(`matters.py:214` — `SupabaseMaskStore(service_client())`;
`contracts.py:335` — `db=None` from its router, defaulting internally
to `service_client()`); this was an isolated deviation in
`case_analysis.py`, not a systemic pattern. Fixed by changing
`case_analysis.py:267` to `SupabaseMaskStore(service_client())`,
mirroring the established convention, and correcting a stale
`app/db.py` module docstring that incorrectly listed `pii_mask` under
`user_client()`'s intended use (plausibly the source of the original
mistake). Re-verified with a second real smoke test end-to-end: matter
→ 2 parties → fact → limitation → forum → case analysis returned
`201 Created` (model `gemini/gemini-2.5-flash`), with the
`litigation_case_analyses` row and 9 `pii_masks` rows both confirmed
persisted via direct service-role query, and party names correctly
round-tripped (masked in the LLM prompt, restored in the response).
Full backend suite (215 tests) re-run clean; the one e2e failure
(`test_no_auto_pdf_download.py`) is a pre-existing, unrelated Playwright
test requiring a running frontend dev server, not started this session.
*Source: Sprint D1 smoke test, 8 August 2026 — found via a real HTTP
call against production, not inferred from code reading; fixed same
day at the user's explicit approval, as a scoped exception to the
sprint's "no feature development" rule given it left the product's
core AI Case Analysis feature completely non-functional in production.*

**TICKET-15: PII auto-detection over-masks some non-name tokens as
`PARTY` entities.** Observed during TICKET-14's re-verification: the
`pii_masks` table for the retest matter contained plausible entries
(`PARTY_A` → "Smoke Test Petitioner", `ADDR_1` → "Delhi") alongside
implausible ones — `PARTY_D` → "Smoke Retest", `PARTY_E` → "Money
Recovery", `PARTY_H` → a truncated fragment starting "National
Commi...". `case_analysis.py` calls `generate(..., auto_detect_names=
True)`, and the NER-based auto-detector appears to be flagging
capitalized multi-word phrases in the narrative/statute-context text
(a matter title fragment, a suit-category string, a statute-corpus
excerpt) as person/entity names. Not a correctness-breaking bug — the
LLM output was still coherent and the real party names were masked and
restored correctly — but it does mean some non-sensitive text is being
needlessly round-tripped through the mask/unmask pipeline, and in a
worse case could over-mask a genuine statutory term inside the
retrieved-chunk context passed to the LLM, degrading the model's
grounding on that chunk. Classification: **Minor**. Not investigated
further this sprint (out of scope for Sprint D1's infrastructure focus,
and orthogonal to TICKET-14's RLS fix).
*Source: Sprint D1 smoke test re-verification, 8 August 2026 — direct
inspection of the real `pii_masks` rows written during the retest.*

## Litigation — Open (not yet fixed)

**TICKET-7: Uttar Pradesh and Bihar have no entry in `forum.py`'s
`STATE_PECUNIARY_LIMITS`.** `STATE_PECUNIARY_LIMITS` covers only Delhi,
Maharashtra, Karnataka, and a generic `DEFAULT`. Uttar Pradesh is one of
exactly three states named as in-scope for Phase 1 in `CLAUDE.md`
Decision 2 (Delhi, Maharashtra, UP) — its absence here means a UP matter
silently returns generic, non-UP-specific court names under the same
`"Deterministic"` confidence label as a properly-modeled state, with no
visual or data distinction. Separately, `ForumAdvisorResponse` has no
field corresponding to `CLAUDE.md`'s own stated fallback policy for
out-of-scope states ("fall back to Central law + a verify state rules
flag") — there is currently no "verify state rules" flag anywhere in the
response shape for *any* state, in scope or not. Decide: (a) add a real
UP pecuniary table entry to close the Decision-2 gap, and (b) add an
explicit `state_rules_verified: bool` (or similar) field to
`ForumAdvisorResponse` so the DEFAULT-fallback case is visibly
distinguishable from a properly-modeled one, rather than silently
indistinguishable. Not fixed alongside TICKET-5/TICKET-6 — this is a
scope decision (which states to model, and how to represent
"unverified"), not a bug with an obvious one-line fix.
*Source: `docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`
scenarios PROP-01/PROP-04/RERA-02/IA-02, 6 August 2026.*

**TICKET-8: AI Case Analysis has no path from `litigation_hearings` into
the LLM prompt.** `api/app/services/case_analysis.py::_facts_narrative()`
builds the text sent to the LLM from matter metadata, parties, and
chronological facts only. `generate_case_analysis()` fetches
`litigation_hearings` solely to answer one deterministic yes/no check
("does at least one hearing exist?") for the Missing Information seed
list — hearing content (dates, IA numbers, purpose of hearing) is
otherwise completely invisible to every section of the analysis. This is
a systemic gap for the entire Interim Applications category: a matter
with an urgent, days-away interim-application hearing produces an AI Case
Analysis that says nothing about it at all. Fix direction: extend
`_facts_narrative()` (or add a parallel section) to include upcoming/
recent hearing docket entries, so time-sensitive procedural context
reaches the LLM the same way chronological facts do. Not fixed alongside
TICKET-5/TICKET-6 — this is a design gap requiring a prompt/narrative
change and its own review, not a one-line arithmetic or ordering fix.
*Source: `docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`
scenarios IA-01/IA-02/IA-03, 6 August 2026.*

**TICKET-7 (lower priority — scope decision, not a bug): Uttar Pradesh and
Bihar have no entry in `forum.py`'s `STATE_PECUNIARY_LIMITS`.**
`STATE_PECUNIARY_LIMITS` covers only Delhi, Maharashtra, Karnataka, and a
generic `DEFAULT`. Uttar Pradesh is one of exactly three states named as
in-scope for Phase 1 in `CLAUDE.md` Decision 2 (Delhi, Maharashtra, UP) —
its absence here means a UP matter silently returns generic,
non-UP-specific court names under the same `"Deterministic"` confidence
label as a properly-modeled state, with no visual or data distinction.
Separately, `ForumAdvisorResponse` has no field corresponding to
`CLAUDE.md`'s own stated fallback policy for out-of-scope states ("fall
back to Central law + a verify state rules flag") — there is currently no
"verify state rules" flag anywhere in the response shape for *any* state,
in scope or not. Decide: (a) add a real UP pecuniary table entry to close
the Decision-2 gap, and (b) add an explicit `state_rules_verified: bool`
(or similar) field to `ForumAdvisorResponse` so the DEFAULT-fallback case
is visibly distinguishable from a properly-modeled one, rather than
silently indistinguishable.
*Source: `docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`
scenarios PROP-01/PROP-04/RERA-02/IA-02, 6 August 2026.*

**TICKET-8 (design gap, not a code bug): AI Case Analysis has no path
from `litigation_hearings` into the LLM prompt.**
`api/app/services/case_analysis.py::_facts_narrative()` builds the text
sent to the LLM from matter metadata, parties, and chronological facts
only. `generate_case_analysis()` fetches `litigation_hearings` solely to
answer one deterministic yes/no check ("does at least one hearing
exist?") for the Missing Information seed list — hearing content (dates,
IA numbers, purpose of hearing) is otherwise completely invisible to
every section of the analysis. This is a systemic gap for the entire
Interim Applications category: a matter with an urgent, days-away
interim-application hearing produces an AI Case Analysis that says
nothing about it at all. Fix direction: extend `_facts_narrative()` (or
add a parallel section) to include upcoming/recent hearing docket entries,
so time-sensitive procedural context reaches the LLM the same way
chronological facts do.
*Source: `docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`
scenarios IA-01/IA-02/IA-03, 6 August 2026.*

## Retrieval

**Cross-encoder reranker over top-K bi-encoder candidates.** The
bi-encoder-only retrieval missed the correct statute chunk in golden
test GT-02; a reranking pass over the top-K candidates was the deferred
fix, accepted alongside the 4/5 golden-recall Sprint 1 signoff.
*Source: Sprint 1 signoff, GT-02 diagnosis.*

**Section semantic tags via Nitesh clause review.** The other deferred
option investigated for the same GT-02 retrieval gap — tagging statute
sections with semantic labels (via Nitesh's own review pass) rather
than relying on term-matching alone. Deferred alongside the reranker
ticket above; the two are alternative or complementary fixes to the
same underlying miss, not yet decided against each other.
*Source: Sprint 1 signoff, GT-02 diagnosis.*

## Statute ingestion

**Statute ingestion regex for state-amendment-appendix handling.**
Found during the India Code corpus ingestion diagnosis — some source
PDFs carry state-amendment appendices in a shape the current ingestion
regex doesn't cleanly separate from the main statutory text. Needs a
dedicated parsing rule, not yet scoped in detail.
*Source: Sprint 2 Deliverable 1, statute ingestion diagnosis.*

## Contracts — clause review integrity

**`content_hash` on `clause_reviews`.** A clause's `review_status` can
go stale silently: re-seeding a template only ever writes
`source_text`/`current_text`, never `review_status`, so a clause
reviewed and marked "kept" keeps that badge even after its actual text
is substantively rewritten underneath it. Caught live — NDA's recitals
clause was reviewed "kept" on 2026-08-01, then rewritten by the
party-names bug fix later that same day, and stayed marked "kept" until
an audit sweep found it. Proposed fix: store a hash of
`template_clauses.current_text` at review time; flag rows where it no
longer matches current content as "reviewed against different content,"
without auto-invalidating on trivial rewording. Already filed as
TICKET-4 in a comment on `migrations/0007_contracts_clause_review.sql`.
*Source: Sprint 2 audit sweep, 2026-08-02.*

**~~Re-seeding silently overwrites a human redraft's `current_text`~~ —
SHIPPED 2026-08-02, not deferred.** Found while designing the bulk-keep
safety scope; escalated by the user from a Sprint 3 ticket to an
immediate fix once Nitesh's real review session was imminent. Every
seed script's upsert previously set `current_text = source_text`
unconditionally on every re-seed, for every clause — including ones
already reviewed, silently destroying a redraft even on a no-op re-run
with review_status still reading `'kept'`/`'redrafted'` as if nothing
happened. Fixed via `_write_clauses_preserving_review()` (canonical
docstring in `scripts/seed_service_agreement_template.py`, duplicated
identically across all 5 seed scripts, matching the
`_prune_orphaned_clauses` convention): clauses with `review_status in
('kept', 'redrafted')` are excluded from the normal upsert entirely
(current_text/review_status never touched, only structural fields
refreshed); if such a clause's incoming `source_text` differs from
what's stored, the ENTIRE seed run halts (raises
`ReviewedClauseConflict`, no partial writes) before touching anything —
deliberately strict over lenient, per explicit user decision. 3 new
tests + a live verification against the real NDA template (marked a
clause "kept," confirmed a modified re-seed halts cleanly with zero
writes, reverted, confirmed normal re-seed resumes and preserves the
kept clause). Still related to TICKET-4 above but distinct: TICKET-4 is
about *detecting* staleness after the fact for clauses where source_text
legitimately changed; this fix is about the seed script never being
allowed to destroy reviewed content in the first place.
*Source: Batch 4.5 design discussion escalated by the user, 2026-08-02.*

**Lever 2 — cross-template shared-clause recognition on the review
screen.** When Service Agreement's Confidentiality clause was seeded, it
was near-verbatim to NDA's. On the clause-review screen, detect and
surface "This clause text is identical to (or 95%+ similar to) reviewed
clause X in Template Y — keep, same as X?" with a one-click accept.
Most useful for Definitions, No License, and Miscellaneous, which repeat
near-verbatim across most templates. This is the lightweight, read-side
version of the "shared clause library formalization" ticket below — ship
the *detection* now; the write-side hoisting into an actual shared
source can wait until the library ticket's own bar is met.
*Source: user's review-velocity request, 2026-08-02 (Lever 2 of 3;
Lever 1 — bulk-keep boilerplate — shipped same day, see
`app/services/contracts.py::bulk_keep_boilerplate_clauses`).*

## Contracts — review UX (note, not a scoped ticket)

**Lever 3 — review sequencing recommendation.** Present clauses in an
order optimized for reviewer time: shared `fixed_boilerplate` clauses
first (reviewed once, applies everywhere — now partly addressed by
Lever 1's bulk-keep), `llm_fillable` clauses last (genuinely bespoke per
template). The admin template-index page could surface something like
"Start here — N clauses shared across M templates need one review
each." Lighter than a scoped ticket — captured here as a direction, not
a spec, since Lever 2 (shared-clause detection) needs to exist first to
make "shared across M templates" a real, computable claim rather than
an assertion. See also the inline note in
`web/src/app/admin/templates/[key]/page.tsx`.
*Source: user's review-velocity request, 2026-08-02 (Lever 3 of 3).*

## Contracts — clause classification

**Governing Law: `llm_fillable` → `fixed_boilerplate` conversion,
across all four templates (NDA, Service Agreement, Consultancy, MoU).**
Live MoU E2E produced a Governing Law clause that blended both branches
of its own if/else instruction — stating both "the courts at Delhi have
exclusive jurisdiction" *and* "disputes shall be referred to
arbitration... seated at New Delhi" in the same clause, despite
`arbitration: True` being unambiguous. Root cause: Governing Law's
actual content is "pick state + pick courts-vs-arbitration + substitute
seat" — three variables, one branch, no narrative judgment — which
never should have qualified as `llm_fillable` under this project's own
bar. Converting to `fixed_boilerplate` with a Jinja `{% if arbitration %}`
branch makes it deterministic (can't blend) and drops one LLM call per
draft — roughly a 20% cost/latency reduction on every contract
generated, since Governing Law is one of the fewer clauses no template
avoids. **Formal bar established from this finding, apply to all future
clause classification:** "does this clause require synthesizing free
prose from the intake inputs, in a way a template author cannot
enumerate in Jinja?" If no, it's `fixed_boilerplate`.
*Source: MoU live E2E, 2026-08-02.*

## Contracts — intake UX

**Field grouping in intake schema.** Service Agreement's ~20-field
intake form is a single long scroll with no section breaks — flagged as
a UX finding at Batch 1 signoff, not fixed at the time. Worth grouping
fields (Parties / Scope / Payment / IP / Confidentiality / Term &
Governing Law, or similar) once more than one template has this many
fields, rather than a one-off fix.
*Source: Sprint 2 Batch 1 (Service Agreement) signoff.*

## Contracts — schema/data model cleanup

**`templates.variant_field` cleanup — redundant with generalized
`applicable_condition`.** Migration 0008 generalized clause inclusion
to the `{field, equals}`/`{field, not_equals}` `applicable_condition`
shape, replacing NDA's one-off `applicable_variant` column. NDA's
`variant_field` is now only used for one narrower legacy purpose —
gating `_variant_role_labels()`'s mutual/one-way role-label derivation
— while every other template's variant-style clause selection
(Consultancy's and MoU's confidentiality direction, Service Agreement's
would-be equivalents) goes through `applicable_condition` directly with
no need for a `variant_field` concept at all. Worth deciding whether to
fold `_variant_role_labels()` into the same generic mechanism (removing
`variant_field` entirely) or leave it as NDA's own special case.
*Source: identified during Batch 2/3 design work, not yet actioned.*

## Contracts — clause library

**Shared clause library formalization.** Several clauses (Miscellaneous
boilerplate structure, the Confidentiality applicable_condition-per-
variant pattern) are now hand-duplicated near-verbatim across multiple
seed scripts rather than sourced from one shared module. Worth
formalizing into a shared library once enough templates reuse the same
boilerplate that hand-duplication becomes a real maintenance cost —
currently 3 templates share the confidentiality-variant pattern
closely enough to matter, not yet enough to justify the abstraction.
Revisit once a 4th genuinely reuses the same clause text, not just the
same mechanism.

## Litigation — AI Case Analysis quality (found Sprint 3.5.6 certification round)

**TICKET-16: Statute corpus covers only 6 acts / 633 chunks — missing
the acts litigation depends on most.** Classification: **Major**. A
direct query of the live `statute_chunks` table during the Sprint 3.5.6
certification round returned exactly Indian Contract Act 1872 (178
chunks), Transfer of Property Act 1882 (129), Consumer Protection Act
2019 (107), Registration Act 1908 (102), Indian Stamp Act 1899 (95),
Carriage by Road Act 2007 (22). **Missing entirely:** the Limitation Act
1963 itself, the Specific Relief Act 1963, the Code of Civil Procedure
1908, the Indian Easements Act 1882, the RERA Act 2016, and the
Commercial Courts Act 2015 — the acts the Acceptance Testing Guide
names as the legally correct basis for a majority of its 26 scenarios.
This explains most of the "Applicable Statutes surfaced something
irrelevant or nothing at all" observations across that round. Fix:
ingest these acts via the existing `scripts/ingest_statutes.py`
pipeline (no new engineering required, a data-sourcing task). Priority:
before Sprint 3.6 (Pleading Generation) reaches its first real drafting
milestone, since pleading generation leans on statute grounding even
more than case analysis does.
*Source: `docs/40_Validation/Sprint_3.5.6_Certification_Report_2026-08-09.md`.*
**Status update (Sprint 3.6 Phase 1, 9 Aug 2026):** corpus expanded to 12
acts / 1,911 chunks — all 6 missing acts ingested from real India Code
PDFs, plus a real chunking-regex bug found and fixed along the way
(footnote-marker-prefixed amended sections were silently dropped; affected
CPC's Order VI Rule 2 and Order VIII Rule 1 specifically). Recall@8
measured at 73%, up from 35% before. **Not fully closed** — 73% recall
means over a quarter of real fact patterns still don't surface the
correct act; see `docs/40_Validation/Sprint_3.6_Phase1_Foundation_Report_2026-08-09.md` §3 for the measurement and the corpus-imbalance side effect it also surfaced.

**TICKET-17: Citation Verifier shows real, reproducible non-determinism.**
Classification: **Major**. During the live CIV-03 scenario, the model
proposed *Anathula Sudhakar v. P. Buchi Reddy (Dead) by LRs and Ors.* —
a real Supreme Court case — and `verify_citation()` returned
`status: "unverified"`. An independent direct re-call of the identical
function with the identical case-name string, minutes later, returned
`status: "verified"` with a real doc URL
(`https://indiankanoon.org/doc/540361/`). Same code, same input,
different result — points to the underlying Indian Kanoon search
ranking being non-deterministic call-to-call, which the confidence
gate's word-overlap threshold (`_best_match`, 0.6) is fully exposed to.
Directly affects Hard Rule 1. Not investigated further this round
(Category B, document-only per this sprint's Defect Policy).
*Source: same as above.*
**Status: CLOSED (Sprint 3.6 Phase 1, 9 Aug 2026).** Root cause fixed:
`verify_citation()` previously cached *any* result forever, verified or
not, so a single transient miss became a permanent wrong answer. Now only
a cached `status="verified"` row is trusted as final; a cached
`"unverified"` row gets one fresh live re-attempt before falling back to
it. Live-confirmed against real production infrastructure (not just a
unit test) — see `Sprint_3.6_Phase1_Foundation_Report_2026-08-09.md` §6.
Confidence reporting also added (`match_confidence`, migration 0017).

**TICKET-18: Some real, correctly-named precedents fail to verify even
on retry.** Classification: **Minor**. *Fateh Chand v. Balkishan Dass*
(landmark 1963 SC authority, proposed in CONT-03) and *Ambrish Kumar
Shukla & Ors. v. Ferrous Infrastructure (P) Ltd.* (real NCDRC landmark,
proposed in RERA-03) both independently re-verified as unverified —
apparently a genuine Indian Kanoon search/title-matching gap for older
Supreme Court judgments and NCDRC-tier orders, distinct from TICKET-17's
flakiness. Safe-failure direction (never renders a fake case as real),
but under-serves the advocate on well-established precedent.
*Source: same as above.*

**TICKET-19: Model sometimes proposes a real but substantively
irrelevant "famous case."** Classification: **Minor**. IA-02 proposed
the *Best Bakery Case* (a real, famous case about witness intimidation
in a criminal trial) to support a civil status-quo application, with a
near-meaningless justification ("highlights the importance of fair
procedure"). The guide's §4.5 specifically flags this risk pattern as
worth recording; this is the first live confirmation of it.
*Source: same as above.*

**TICKET-20: `gemini-2.5-flash-lite` shows materially weaker/confused
legal reasoning than `gemini-2.5-flash` on the same task type.**
Classification: **Major**. APP-01/02/03 (all served by flash-lite, see
TICKET-21) show the model reasoning about ordinary CPC first appeals as
though Consumer Protection Act consumer-forum appellate provisions
(District Commission → State Commission, 45-day period) might govern —
because that was the only appeal-shaped content the corpus (see
TICKET-16) had to retrieve, and flash-lite did not reliably override
with correct background legal knowledge the way flash consistently did
elsewhere in the same round. `possible_causes_of_action` came back
empty for all three. Compounds TICKET-16; also a standalone model-choice
finding.
*Source: same as above.*
**Status update (Sprint 3.6 Phase 1, 9 Aug 2026):** partially addressed
via TICKET-16's corpus fix — a fresh case analysis for APP-01 on the
expanded corpus now correctly retrieves `Code of Civil Procedure, 1908,
Order XLI Rule 37` (the real, correct appellate provision) instead of
Consumer Protection Act content, and a pleading outline built from that
fresh analysis correctly frames the issue as "Appeal against District
Court decree" with no CPA confusion — a full, demonstrated resolution for
this specific scenario. **Not closed generally** — this was one
scenario's fix verified, not a systematic guarantee the same confusion
can't recur elsewhere the corpus still has gaps (TICKET-16 is at 73%
recall, not 100%). See `Sprint_3.6_Phase1_Foundation_Report_2026-08-09.md` §7.

**TICKET-21: Model-tier degradation (pro → flash/flash-lite) is
completely silent to the advocate.** Classification: **Major**. Every
one of the 26 real `generate()` calls in the Sprint 3.5.6 round first
attempted `gemini-2.5-pro` and was rate-limited (52 confirmed
`status=error reason="gemini: rate limited"` log lines) — `gemini-2.5-pro`
served zero real requests the entire round. Nothing in the API response,
the persisted `litigation_case_analyses` row, or the reviewed frontend
surfaces which tier actually produced a given analysis. Combined with
TICKET-20, this means an advocate has no way to know a given analysis
came from a materially weaker model.
*Source: same as above.*
**Status: CLOSED as "no longer silent" (Sprint 3.6 Phase 1, 9 Aug 2026),
but see the new capacity concern this closure itself surfaced.**
`GenerationResult` now carries `requested_model`/`degraded`/
`fallback_chain` explicitly; an explicit `MODEL DEGRADED` warning-level
log line fires on every downgrade; `litigation_case_analyses` was
retrofitted with a `model_routing` column (migration 0016), not just the
new pleading table. Making this visible revealed something new and
concerning, not previously quantified: in Sprint 3.6 Phase 1's own
evaluation, every one of 6 real pleading-outline generations degraded
past `gemini-2.5-flash`/`flash-lite` all the way to Groq — worse than the
certification round. Plausibly cumulative free-tier rate-limit pressure
from this project's own heavy same-day real-call volume, not a code
regression, but a real capacity-planning question before Sprint 3.6
Phase 2 assumes case-analysis-round quota margins hold for
pleading-generation-round volumes too. See
`Sprint_3.6_Phase1_Foundation_Report_2026-08-09.md` §5/§8.

**TICKET-22: LLM Gateway success-path logs are suppressed by the
effective logging configuration.** Classification: **Minor**. 52
`WARNING`-level failure log lines were captured live; zero `INFO`-level
success log lines were, despite 26 real successful generations —
`generate()`'s success path logs at `INFO` (`llm_gateway.py` ~line 273),
which the app's effective logging level does not surface in practice.
The module's own docstring claim ("every attempt is logged... for
auditability") does not hold operationally for successes today, though
Hard Rule 4's actual DB-level requirement is independently met via the
`litigation_case_analyses` row.
*Source: same as above.*
**Status: CLOSED (Sprint 3.6 Phase 1, 9 Aug 2026).** `app/main.py` now
explicitly configures the `vidhidesk.*` logger hierarchy at `INFO` with a
real handler at startup. Confirmed live: both `status=ok` and the new
`MODEL DEGRADED` lines (TICKET-21) are now actually emitted, not just
logged-and-discarded.

**TICKET-23: No token-usage or cost capture anywhere in the LLM
Gateway.** Classification: **Enhancement**. `GenerationResult`
(`llm_gateway.py`) carries `text`, `provider`, `model`, `latency_ms`,
`masked_prompt` — no token-count field, and none of Gemini's, Groq's,
or SambaNova's raw response bodies are parsed for usage data anywhere
in the codebase. This made real cost-per-request/per-scenario reporting
impossible in the Sprint 3.5.6 certification round (correctly reported
as "not measured," not estimated).
*Source: same as above.*

## Litigation — Clause-Based Drafting Engine (found Sprint 3.6 Phase 2 live evaluation)

**TICKET-24: PII auto-mask placeholder leaked into final, unmasked clause
text.** Classification: **Major** (upgrades TICKET-15's "Minor, cosmetic"
finding — this is the same over-masking root cause producing a directly
user-visible corruption, not just a harmless extra round-trip). Live
evaluation of `clause_generator.py`'s `facts` generator against the real
CIV-01 matter produced version 1 text reading `"...annexed herewith as
Exhibit PARTY_I2"` / `"Exhibit PARTY_I1"` — a raw, internal PII-mask
placeholder token, never restored to the real exhibit label (`Exhibit
P-2`/`Exhibit P-1`), visible directly in advocate-facing drafted clause
text. A second, independent generation of the same clause (version 2, same
matter, same context) did NOT reproduce the corruption and correctly read
`Exhibit P-2`/`Exhibit P-1` — confirming this is the same non-deterministic
auto-detection behavior TICKET-15 already found (the NER-based
`auto_detect_names` flagging a non-name token, here plausibly the exhibit
label text embedded in `_facts_context()`, as a `PARTY`-kind entity),
not a deterministic bug reproducible on every run. Not fixed this sprint
per the Defect Policy (Category B, document-only). Fix direction: either
tighten `auto_detect_names`'s NER filtering to exclude short
alphanumeric-with-hyphen tokens (exhibit labels, case numbers), or exclude
exhibit-number strings from the auto-detection pass entirely in
`clause_generator.py`'s prompt-building (they are already structured data,
not free text needing NER).
*Source: Sprint 3.6 Phase 2 live evaluation, matter CIV-01 (real production
data), 9 August 2026 — see `docs/40_Validation/Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md` §5.*

**TICKET-25: `legal_grounds` clause generator has a disproportionate
malformed-JSON failure rate.** Classification: **Major**. Live evaluation
across 6 real matters: `legal_grounds` failed to parse as valid JSON in
2/6 runs (33%) — COM-01 and PROP-03 — the highest failure rate of any of
the 5 LLM clause generators (all others: 0/6). `legal_grounds`'s prompt is
also the longest/most context-dense of the five (legal issues + causes of
action + statute context + case-law context in one call), and both
failures happened on `gemini-2.5-flash-lite` (the weaker fallback tier —
consistent with, though not proven to share the same cause as, Phase 1's
TICKET-20 "flash-lite shows materially weaker reasoning" finding). Not
investigated further this sprint (Category B, document-only). Fix
direction: either shorten/simplify the `legal_grounds` prompt, or route it
preferentially to a stronger model tier if/when the LLM Gateway supports
per-task-type tier preference (it currently does not — every task_type
shares the same provider/model failover pool).
*Source: Sprint 3.6 Phase 2 live evaluation, 9 August 2026 — see
`Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md` §5/§6.*
**Status: SUBSTANTIALLY RESOLVED (Sprint 3.6 Phase 2A, 9 August 2026)**, root
cause found and fixed, not just worked around. Regenerating the ONE known
malformed sample's raw text live (Phase 2 never persisted it) found a
literal, unescaped newline inside a JSON string value — not a structural
JSON error. A targeted follow-up reproduced the EXACT trigger 3/3 times on
the same matter/model: the model copying a text span across an ambiguous
prompt-section boundary (including the literal blank-line separator)
directly into a field value. Fixed by (a) restructuring `legal_grounds`
from one free-form "content" string into a structured, per-issue "grounds"
list (shorter fields = less surface area for the same failure class), (b)
explicit `=== SECTION ===` delimiters + an explicit "copy the issue
verbatim from exactly one bullet" instruction, re-verified 3/3 fixed on the
identical reproducing case, and (c) two gateway-level structural defenses
applied to all 5 LLM clause types: native provider JSON-mode
(`generate_json()`, `llm_gateway.py`) and one automatic, PII-safe repair
retry on a still-malformed response. Full 6-matter regression: 0/6
malformed (target was <5%), up from 33%. **Not fully closed**: this
session's Gemini quota was exhausted after the diagnostic work, so the fix
could only be regression-tested against Groq — the specific
`gemini-2.5-flash-lite` tier responsible for 100% of known failures to
date was not re-tested. Close once a `gemini-2.5-flash-lite`-targeted
re-run (`api/scripts/diagnose_legal_grounds_flash_lite.py`, already built)
confirms the same result on that tier. See
`Sprint_3.6_Phase2A_Legal_Grounds_Report_2026-08-09.md`.

**TICKET-26: Most LLM-drafted clauses claim zero statute/case-law
references, even when grounding material was available.** Classification:
**Minor** (safe-by-construction — an LLM clause that claims nothing is
never wrongly trusted, since there is nothing to ground; the gap is
missed grounding *coverage*, not incorrect grounding). Live evaluation:
of 24 LLM clause runs eligible to cite something (excluding `facts`/
`prayer`, whose prompts don't ask for citations by design), only 6/24
claimed any statute ref at all — `cause_of_action` cited a statute in
just 2/6 runs despite every one of those 6 matters having at least one
applicable statute available in its outline. `legal_grounds` and
`reliefs`' prompts do not explicitly instruct the model to actively
attempt a citation for every relevant claim, only to cite one if it
appears in context — worth tightening prompt language to push for higher
grounding *attempts* (never at the cost of Hard Rule 3's "never invent
one" guarantee). Separately and NOT part of this ticket: 0/24 case-law
refs were claimed at all, which is fully explained by the same 6 matters'
outlines all having empty `applicable_case_law` (Phase 1's already-open,
still-unresolved case-law-recall gap, Foundation Report §9 point 3) —
correct behavior given empty upstream data, not a new defect.
*Source: same as TICKET-25.*
**Not closed, incidental partial improvement noted (Sprint 3.6 Phase 2A,
9 August 2026):** `legal_grounds`'s own statute-citation-attempt rate rose
from 50% to 67% of attempts (§5 of the Phase 2A report) as a side effect of
its redesigned, more explicit prompt structure — not a deliberate fix for
this ticket, and `cause_of_action`/`reliefs`'s own prompts were not
touched. Remains open for those two clause types; not re-measured this
sprint per its own "do not optimize prematurely" instruction.

**TICKET-27: Clause regeneration is not guaranteed to reuse the same
underlying model tier, and can therefore produce materially different
prose on the same context.** Classification: **Minor** (expected
consequence of the existing failover architecture, not a bug in the
clause engine itself — flagged as a UX/expectation-setting gap). Live
evaluation: regenerating the `facts` clause a second time (same matter,
same context, minutes apart) sometimes landed on a different model in the
failover chain than the first generation did, because real-time
Gemini rate-limit state shifted between the two calls (see TICKET-21/§7 of
the Phase 2 report for the underlying capacity pressure). An advocate
clicking "Regenerate" on a clause with an eye toward "get a slightly
different phrasing of the same facts" has no way to know whether the
regeneration came from the same model tier as the original — worth
surfacing `model_used` prominently in a future Human Review UI so this is
visible, not fixing at the gateway level (the failover behavior itself is
correct and intentional).
*Source: same as TICKET-25.*
*Source: observed across Batches 1-3 (Service Agreement, Consultancy, MoU).*
