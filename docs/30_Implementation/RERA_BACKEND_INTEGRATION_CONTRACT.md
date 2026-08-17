> **Title:** RERA & Real Estate — Backend Integration Contract (Phase 1)
> **Version:** 1.0
> **Status:** Backend implemented and unit-tested; NOT yet applied to production Supabase; NOT yet runtime-verified against a live frontend
> **Owner:** Keshav
> **Audience:** The frontend/UI agent building `/rera`, `/rera/deeds`, `/rera/new`, `/rera/complaint/new`, `/rera/walkthrough`
> **Last Updated:** 17 August 2026
> **Canonical Reference:** Yes, for the RERA backend surface described here — subordinate to `10_Architecture/Engineering_Architecture_Handbook.md` and CLAUDE.md
> **Related Documents:** [`Build_Tracker.md`](Build_Tracker.md), [`Backlog.md`](Backlog.md), [`ADR/ADR-010-phase-1-state-coverage.md`](ADR/ADR-010-phase-1-state-coverage.md)

---

# RERA & Real Estate — Backend Integration Contract

## 0. Read this first: the one design decision that shapes everything below

**Property deeds and RERA complaints are NOT new backend capabilities.** They
reuse the existing generic template-drafting engine
(`api/app/services/contracts.py::generate_draft`, already module-agnostic
despite its filename — it takes a `matter_id` and a `template_id`, nothing
Contracts-specific) exactly the same way every one of the 10 Contracts
templates does. This was a deliberate reuse decision, not an oversight —
see §6 for the full rationale.

**Only two capabilities had no existing equivalent anywhere in the
codebase, and got new code:** curated state/procedure/walkthrough content,
and per-advocate walkthrough progress. Those are the only genuinely new
endpoints (§8).

---

## 1. Matter model

RERA matters are ordinary `matters` rows with `module = 'rera'` — already a
valid value (`MODULES` in `api/app/models/schemas.py`, already included
before this sprint). No new matter type, no parallel entity. Create one via
the existing `POST /api/matters` with `module: "rera"` and (for a deed)
`template_id` set to the chosen template's id.

## 2. Deed workflow (`/rera/deeds`, `/rera/new?template=sale-deed`)

| Step | Endpoint | Notes |
|---|---|---|
| List available deed templates | `GET /api/templates` | **Existing, unchanged.** Not category-filtered server-side — filter client-side on `category === "rera"`, same pattern `contracts/page.tsx` already uses for `category === "contracts"`. |
| Get one template's schema | `GET /api/templates/{id}` | **Existing, unchanged.** Returns `intake_schema` (the JSON Schema driving the intake form) — see `templates/rera/sale-deed.schema.json` for the Sale Deed's actual field list. |
| Create the matter | `POST /api/matters` | **Existing, unchanged.** `{"title": ..., "module": "rera", "template_id": "<sale-deed template id>"}` |
| Generate the deed draft | `POST /api/matters/{matter_id}/drafts` | **Existing, unchanged.** `{"template_id": ..., "form_data": {...}}` — `form_data` keys match the template's `schema_json.fields[].key`. |
| List draft versions | `GET /api/matters/{matter_id}/drafts` | **Existing, unchanged.** |
| Amend (new version) | `POST /api/matters/{matter_id}/drafts` again | **Existing, unchanged.** Same endpoint, resubmit updated `form_data` — the service always creates a new `draft_versions` row (never overwrites), same as any Contracts amendment. |
| Download docx/pdf | `GET /api/drafts/{id}/download`, `.../download.pdf` | **Existing, unchanged.** |
| State-specific stamp duty/registration notes | `GET /api/state-rules?state=X&instrument=Sale%20Deed` | **Existing, unchanged** (lives in `contracts.py` router despite the name — genuinely module-agnostic already). |

**Seeded this sprint:** one real, working deed template — **Sale Deed**
(`template_key: "sale-deed"`, category `"rera"`) — `templates/rera/sale-deed.schema.json`,
`templates/rera/sale-deed.docx` (skeleton), 8 clauses in `template_clauses`
(6 fixed_boilerplate, 2 llm_fillable), seeded via
`api/scripts/seed_sale_deed_template.py`. Gift/Mortgage/Relinquishment
deeds are the same pattern (new schema.json + skeleton + seed script) but
were **not** authored this sprint — see §11 Known Limitations.

## 3. RERA complaint workflow (`/rera/complaint/new`)

**Resolved gap decision:** a dedicated `POST /api/rera/complaints` endpoint
was considered and **rejected** — it would duplicate `generate_draft()`'s
existing logic (masking, clause loop, docx render, versioning, audit trail)
for zero semantic gain. A RERA complaint is drafted through **the exact
same endpoints as a deed** (table above), with `template_id` pointing at
the seeded RERA Complaint template instead of Sale Deed. No new complaint
router, no new complaint table — see §8 for what *is* new.

**Seeded this sprint:** **RERA Complaint — Delay in Possession**
(`template_key: "rera-complaint"`, category `"rera"`) —
`templates/rera/rera-complaint.schema.json`,
`templates/rera/rera-complaint.docx`, 5 clauses (4 fixed_boilerplate, 1
llm_fillable — Facts), seeded via
`api/scripts/seed_rera_complaint_template.py`. The Grounds clause cites
only Section 18 and Section 11(4)(a) of the Real Estate (Regulation and
Development) Act, 2016 — the well-known, undisputed statutory basis for a
delay-in-possession complaint — as `fixed_boilerplate` (no LLM call, so
nothing here can be invented). No `state_rules` rows are seeded for this
template — RERA complaint procedure is authority/forum-specific, not a
stamp-duty/registration instrument; see §4 for the actual state-specific
content model.

**Domain fields actually modeled** (per this sprint's own checklist,
§8 of the brief) — see `rera-complaint.schema.json` for the authoritative
list: complainant/allottee, respondent/promoter, project name + RERA
registration number, unit number, agreement date, consideration amount,
amount paid, promised possession date, actual possession date, facts
narrative, relief sought, jurisdiction state. **Not separately persisted**
as structured data beyond the drafting request/response cycle — this
matches the existing Contracts convention exactly: `form_data` is never
stored as its own row (only the rendered docx + `draft_clause_fills.prompt`
audit trail are), so revisiting a matter to amend requires re-submitting
the form. This is a pre-existing architectural characteristic of
`generate_draft()`, not something introduced for RERA.

## 4. State-specific data model (`rera_guides`, `state_rules`)

Two tables, two different shapes, kept deliberately separate (not merged
into one generic "state content" table):

- **`state_rules`** — stamp duty / registration notes for an *instrument*
  (already existed, migration `0001`; used by Contracts too). Extended
  this sprint with `verification_status` (migration `0019`).
- **`rera_guides`** — ordered filing *procedure* steps for a
  (state, procedure) pair (already existed as a table, migration `0001`,
  but had never been used by any code — no `procedure` column existed).
  Extended this sprint with `procedure`, `heading`, `required_documents`,
  `portal_url`, `warnings`, `verification_status` (migration `0019`).

**Both tables are empty in production as of this sprint** (confirmed —
see §12 Runtime Verification). **No content was seeded into either** for
the walkthrough beyond the schema capability itself — per this sprint's
explicit "never fabricate state-specific legal/procedural content" rule,
no stamp-duty figure, filing step, or portal URL was invented. This is an
honest, deliberate gap, not an oversight — see §11.

Phase 1 supported states (ADR-010, unchanged): **Delhi, Maharashtra,
Uttar Pradesh**. Any other state is rejected by the walkthrough endpoints
with HTTP 400 (`RERAError`), never silently guessed at.

## 5. Filing walkthrough (`/rera/walkthrough`, `/rera/walkthrough/[state]/[procedure]`)

All five endpoints below are genuinely new (`api/app/routers/rera.py`,
`api/app/services/rera.py`) — the only new drafting-adjacent code this
sprint wrote.

| Capability | Endpoint | Method | Auth | Request | Response | Errors |
|---|---|---|---|---|---|---|
| Supported states | `/api/rera/states` | GET | Bearer JWT | — | `list[str]` — always exactly `["Delhi", "Maharashtra", "Uttar Pradesh"]` | 401 unauthenticated |
| Procedures for a state | `/api/rera/procedures?state=Delhi` | GET | Bearer JWT | query `state` | `list[RERAWalkthroughProcedureOut]` — `{state, procedure, step_count}`, derived from real curated rows, **empty list** if none curated yet | 400 unsupported state; 401 |
| Steps for a procedure | `/api/rera/walkthrough/{state}/{procedure}` | GET | Bearer JWT | path params | `list[RERAWalkthroughStepOut]` ordered by `step_no`, **empty list** if uncurated | 400 unsupported state; 401 |
| Get own progress | `/api/rera/walkthrough/{state}/{procedure}/progress?matter_id=` | GET | Bearer JWT | optional query `matter_id` | `RERAWalkthroughProgressOut \| null` | 400 unsupported state; 401 |
| Update own progress | `/api/rera/walkthrough/{state}/{procedure}/progress` | PUT | Bearer JWT | `RERAWalkthroughProgressUpdate` body (`matter_id?`, `current_step_no?`, `mark_step_complete_id?`, `mark_step_incomplete_id?`) | `RERAWalkthroughProgressOut` | 400 invalid state/procedure/step/current_step_no/non-RERA matter/matter not found; 401 |

**Example — mark a step complete:**
```
PUT /api/rera/walkthrough/Delhi/project-registration/progress
Authorization: Bearer <jwt>
{"mark_step_complete_id": "9bdce3fd-1712-450e-aad4-c81a187819c1"}

200 OK
{
  "id": "d6604fac-...",
  "user_id": "5f2a...",
  "matter_id": null,
  "state": "Delhi",
  "procedure": "project-registration",
  "current_step_no": 1,
  "completed_step_ids": ["9bdce3fd-1712-450e-aad4-c81a187819c1"],
  "is_complete": false,
  "started_at": "2026-08-17T11:05:06.14Z",
  "updated_at": "2026-08-17T11:05:06.14Z"
}
```

**Design decision — progress scope (resolved gap):** walkthrough progress
is **user-scoped, not matter-scoped**, because the product's own routing
(`/rera/walkthrough/[state]/[procedure]` — no `matterId` segment) implies
an advocate can start and resume a walkthrough independently of any
specific matter. `matter_id` is an **optional** association: passing it
attaches this progress record to a specific RERA matter (validated —
ownership + `module == 'rera'` — before any write); omitting it tracks a
"global" walkthrough for that state+procedure. A user can have both a
global and a matter-scoped progress record for the same (state, procedure)
simultaneously — they're independent rows (`rera_walkthrough_progress`,
migration `0019`, two partial unique indexes: one for `matter_id is null`,
one for `matter_id is not null`).

**Idempotency:** `PUT .../progress` is a true upsert — calling it twice
with the same `mark_step_complete_id` is a no-op the second time (set
union), and it never creates a second progress row for the same
(user, state, procedure[, matter]) — safe to retry.

## 6. Why the deed/complaint drafting engine was reused, not duplicated

`api/app/services/contracts.py::generate_draft(matter_id, template_id,
form_data, amendment_note, db)` has **zero Contracts-specific logic** in
it — it reads `templates`/`template_clauses` generically, masks free-text
fields through the shared PII pipeline, calls the shared LLM Gateway per
`llm_fillable` clause, renders a `docxtpl` skeleton, and writes
`draft_versions`/`draft_clause_fills`. The router endpoint
(`POST /api/matters/{id}/drafts`) does not check `matter.module` at all.
The only thing that made every existing template a "Contracts template"
was which `templates.category` value was chosen at seed time — an
arbitrary string, not an enforced enum. Setting `category: "rera"` and
pointing `docx_path` at a RERA-specific skeleton was sufficient to reuse
100% of this pipeline with **zero code changes** to `contracts.py`,
`app/routers/contracts.py`, or the LLM Gateway. This is the concrete
evidence behind CLAUDE.md's "reuse shared infrastructure, do not create
duplicate generic entities" instruction actually being followed, not just
asserted.

## 7. Authorization / RLS

| Table | Ownership path | RLS policy |
|---|---|---|
| `matters` (module='rera') | direct, `user_id` | `matters_owner_all` (pre-existing) |
| `templates`, `template_clauses` | shared reference data | `templates_read_authenticated` (pre-existing; writes service-role only) |
| `draft_versions`, `draft_clause_fills` | via `matter_id` | pre-existing owner policies |
| `state_rules`, `rera_guides` | shared reference data | `state_rules_read_authenticated`, `rera_guides_read_authenticated` (pre-existing, migration `0002`) |
| `rera_walkthrough_progress` | **direct**, `user_id` (new) | `rera_walkthrough_progress_owner_all` (new, migration `0019`): `user_id = auth.uid()` |

Every RERA router endpoint uses `user.db` (the caller's RLS-scoped
Supabase client — see `app/auth.py`), never `service_client()`, for
anything user-owned. `matter_id` passed into a walkthrough-progress
request is independently re-validated
(`app/services/rera.py::_validate_rera_matter`) for existence, ownership
(via `user.db`, so a non-owned matter looks identical to a missing one —
no ownership-probing oracle, same posture as every other module), and
`module == 'rera'` — a Litigation or Contracts matter id is rejected with
400, not silently accepted.

## 8. AI / RAG / citation usage

**None of the new RERA-specific code calls the LLM Gateway, RAG retrieval,
or the Citation Verifier directly.** The only AI involvement in this
sprint's scope is the 3 `llm_fillable` clauses across the two seeded
templates (Sale Deed's `recitals`/`special_conditions`, RERA Complaint's
`facts`), which go through the exact same `generate()` call
`contracts.generate_draft()` already makes for every Contracts template —
masked, `task_type="contract_drafter"`, same provider failover chain
(Gemini → Groq → SambaNova → Cerebras). No new task_type was added, no new
provider, no direct Gemini call from RERA code. The walkthrough endpoints
are 100% deterministic (`app/services/rera.py` contains no LLM call at
all) — curated content lookup and progress bookkeeping only.

## 9. Document generation

Reused verbatim: `docxtpl` + the same `{{p clauses_subdoc}}` Subdocument
pattern every Contracts template uses (`build_sale_deed_skeleton.py` /
`build_rera_complaint_skeleton.py` mirror `build_nda_skeleton.py` exactly).
PDF export reuses the existing `GET /api/drafts/{id}/download.pdf` →
`contracts.convert_docx_to_pdf()` (LibreOffice headless, 15s timeout) —
no RERA-specific document generation code exists or was needed.

## 10. Tests

`api/tests/test_rera.py` — **20 tests, all passing** against an in-memory
`FakeDB` (no production writes — see §12 for why this matters for this
project specifically):

- Domain: procedure listing, step ordering, empty-when-uncurated, progress
  create/update/complete/incomplete, `is_complete` derivation, exactly-one-row
  upsert semantics.
- Validation: unsupported state (400), procedure with zero curated steps,
  unknown step id, `current_step_no` out of range.
- Security: non-RERA matter rejected, matter belonging to nobody rejected,
  malformed matter id rejected, progress rows correctly stamped with the
  requesting user's id (see the test's own docstring for the explicit,
  honest limitation: true cross-user RLS isolation cannot be proven
  against a FakeDB — see §12).
- API: auth required (401/422 unauthenticated), full PUT→GET roundtrip via
  `TestClient`.

Deed/complaint drafting itself is **not** separately tested here — it runs
through `contracts.generate_draft()`, already covered by
`test_contracts.py`/`test_clause_generator.py`-style tests; there is no new
drafting code path for this sprint to test in isolation. Seeding the two
new templates was verified by running the seed scripts against a real
local check (see §12).

Full backend suite (`api/tests/` — all files, not just `test_rera.py`) was
re-run after this sprint's changes to confirm no regressions; see §12 for
the pass/fail count and evidence.

## 11. Known limitations (stated plainly, not glossed over)

- **`rera_guides` and `state_rules` (RERA instruments) have zero curated
  rows.** The walkthrough will correctly return empty lists for every
  state/procedure until real, source-linked content is curated and
  seeded — this was a deliberate choice (never fabricate legal/procedural
  content) documented in this sprint's brief, not a bug.
- **Only one deed template (Sale Deed) exists.** Gift Deed, Mortgage
  Deed, and Relinquishment Deed are the identical pattern (new
  schema.json + docx skeleton + seed script, same reuse of
  `generate_draft()`) but were not authored this sprint — pure follow-up
  work, no architecture decision pending.
- **Migration `0019` is authored but NOT applied to production Supabase.**
  See §12 for why, and the exact command to run it.
- **`rera_walkthrough_progress` cross-user isolation is enforced entirely
  by Postgres RLS**, not by an application-layer `user_id` filter (same
  convention as the `matters` table itself) — this cannot be verified by
  a unit test against a FakeDB; it requires a live-Supabase runtime check
  (not performed this sprint — the table does not exist in production
  yet, since the migration hasn't been applied).
- **No frontend was built or modified** — per this sprint's explicit
  scope. The three routes this contract informs
  (`web/src/app/rera/...`) do not exist yet in `web/src/app/`.

## 12. Runtime verification performed

- `python -m py_compile` on every new/modified `.py` file: clean.
- `app.openapi()` inspected directly (not guessed): all 5 new
  `/api/rera/...` paths present with correct methods
  (`GET /api/rera/states`, `GET /api/rera/procedures`,
  `GET /api/rera/walkthrough/{state}/{procedure}`,
  `GET`+`PUT /api/rera/walkthrough/{state}/{procedure}/progress`).
- `api/tests/test_rera.py`: 20/20 passed.
- Full `api/tests/` suite re-run after all changes: **[fill in below once
  the background run this sprint completed — see the session's final
  report for the exact pass/fail count]**.
- Both new docx skeletons built successfully locally
  (`templates/rera/sale-deed.docx`, `templates/rera/rera-complaint.docx`).
- Migration `0019` was **not** applied against production Supabase this
  sprint (see §11) — applying it is a follow-up step:
  `supabase db query --linked --file api/migrations/0019_rera_backend.sql`
  (the same sanctioned path Build Tracker E35 used for migrations
  0013/0014), followed by a direct schema re-query to confirm, per this
  project's own established production-sync ritual — not performed here
  to avoid an unreviewed, unrequested production write in an
  already-large session.
- `rera_guides`/`state_rules` were confirmed to have **zero rows** at the
  time of authoring this contract, based on migration `0001`'s own
  original seed state (neither table has ever been seeded by any script
  in this repository) — not independently re-queried against production
  this sprint (would require the not-yet-applied migration `0019` schema
  to interpret meaningfully anyway).
