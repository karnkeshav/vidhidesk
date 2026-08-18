> **Title:** Consulting & Legal Research — Backend Integration Contract (Phase 1)
> **Version:** 1.2 (Final Handover — Live Verified)
> **Status:** Backend implemented, unit-tested (19/19 `test_consulting.py`, full suite regression clean), migration `0020_consulting_backend.sql` **applied to the live Supabase database (18 August 2026)**, and live end-to-end verified — 18/18 checks against real production data, including live cross-user RLS isolation at both the API and raw-table level. See §18. Not yet runtime-verified against a live frontend (no Consulting UI built yet).
> **Owner:** Keshav
> **Audience:** The frontend/UI agent building `/consulting`, `/consulting/[matterId]`
> **Last Updated:** 17 August 2026
> **Canonical Reference:** Yes, for the Consulting backend surface described here — subordinate to `10_Architecture/Engineering_Architecture_Handbook.md` and CLAUDE.md
> **Related Documents:** [`Build_Tracker.md`](Build_Tracker.md), [`../00_Product/Product_Vision.md`](../00_Product/Product_Vision.md) Module 4, [`RERA_BACKEND_INTEGRATION_CONTRACT.md`](RERA_BACKEND_INTEGRATION_CONTRACT.md) (same reuse pattern, different module)

---

# Consulting & Legal Research — Backend Integration Contract

## 1. Overview

Consulting is not a new subsystem — it is a new *combination* of six
subsystems that already existed and were already load-bearing elsewhere:
the Matter Engine (`matters`, module-agnostic), the RAG Retriever
(`app/services/retrieval.py::hybrid_retrieve`), the Citation Verifier
(`app/services/citations.py::verify_citation`), the PII Masker
(`app/services/pii_mask.py`), the LLM Gateway
(`app/services/llm_gateway.py::generate_json`, an already-registered
`consulting_analyst` task type), and — when the caller supplies them —
the deterministic Limitation Calculator / Forum Advisor
(`app/services/limitation.py`, `app/services/forum.py`, both pure
functions with no litigation-matter binding). This is the same
composition pattern Litigation's AI Case Analysis already proved out.

The only genuinely new artifact is `consulting_analyses` — a versioned,
structured analysis table, directly mirroring `litigation_case_analyses`
(migration 0014). No new matter table, no new LLM provider, no new
citation verifier, no new PII masking engine.

**Consulting matters are ordinary `matters` rows with `module =
'consulting'`** — already a valid value since migration 0001. No
`consulting_cases`/`consulting_matters` table exists or should be
created. **You do not need to call `POST /api/matters` yourself** —
`POST /api/consulting/analyze` creates the matter for you when no
`matter_id` is supplied.

## 2. Authentication

Standard `Authorization: Bearer <supabase JWT>` header, identical to
every other VidhiDesk endpoint. No unauthenticated access to either
endpoint — a missing/invalid token returns `401`.

## 3. `POST /api/consulting/analyze`

Ask a new legal question (starts a new Consulting matter) or continue an
existing one as a follow-up (new analysis version, same matter — never a
new matter per follow-up).

- No `matter_id` in the body → creates a new `module='consulting'`
  matter, title auto-derived from the question (first 80 characters),
  returns version 1.
- `matter_id` supplied → must be an existing matter the caller owns with
  `module == "consulting"`; creates version 2, 3, … inside that same
  matter.

## 4. `GET /api/consulting/matters/{matter_id}/analyses`

Returns `list[ConsultingAnalysisOut]` for the given matter, most recent
version first (empty list if none yet, `404` if the matter doesn't exist
or isn't owned by the caller). Use this to render `/consulting/[matterId]`'s
history/timeline — same field shapes and rendering rules as §5–§13 below,
for every historical version, not just the newest.

## 5. Request Schema — `ConsultingAnalyzeRequest`

```json
{
  "question": "My washing machine broke within a week and the seller refuses a refund, what law covers this?",
  "matter_id": null,
  "party_names": [],
  "addresses": [],
  "limitation": null,
  "forum": null
}
```

| Field | Required | Notes |
|---|---|---|
| `question` | Yes | 15–4000 characters after trimming. Empty, whitespace-only, or under 15 chars → `422`. No documented exact minimum exists elsewhere in the project docs; 15 was chosen as a reasonable floor for "enough to retrieve against" — a backend implementation detail, not legal content, safe to raise/lower without any migration. |
| `matter_id` | No | Omit to start a new matter. Supply an existing Consulting matter's id for a follow-up. Must belong to the caller and have `module == "consulting"`, or `404`/`400` respectively. |
| `party_names`, `addresses` | No | Same optional PII-masking hints the generic `POST /api/matters/{id}/messages` endpoint already accepts — force-mask specific strings in addition to automatic PAN/Aadhaar/phone/email/name detection. |
| `limitation` | No | Same shape as `CaseAnalysisLimitationInput` (Litigation's `POST /api/litigation/limitation-calculator` response). Supply this when you've already run the Limitation Calculator — the analysis then reports the **deterministic** limitation period instead of the LLM's own advisory guess. |
| `forum` | No | Same shape as `CaseAnalysisForumInput` (Litigation's `POST /api/litigation/forum-advisor` response). Supply this when you've already run the Forum Advisor — the analysis then reports the **deterministic** forum instead of the LLM's own advisory guess. |

**Recommended flow for the strongest answer:** if the question has
enough structure to run the existing Forum Advisor (`suit_type`,
`claim_value_inr`, `jurisdiction_state`) or Limitation Calculator
(`cause_of_action_date`, `suit_category`), call those two existing
Litigation endpoints first and pass their output through as
`forum`/`limitation`. Optional — the analysis works without them, just
with `deterministic: false` fields.

## 6. Response Schema — `ConsultingAnalysisOut` (`201 Created`)

```json
{
  "id": "…",
  "matter_id": "…",
  "version_no": 1,
  "question": "My washing machine broke within a week and the seller refuses a refund, what law covers this?",
  "applicable_law": [
    {"act": "Consumer Protection Act, 2019", "section_no": "35", "relevance": "Governs complaints for defective goods.", "grounded": true}
  ],
  "correct_forum": {
    "forum_name": "District Consumer Disputes Redressal Commission",
    "reasoning": "Claim value within district pecuniary limit.",
    "deterministic": false,
    "source": "llm_advisory"
  },
  "remedies_available": [
    {"remedy": "Refund", "description": "Full refund of the purchase price."}
  ],
  "limitation_period": {
    "summary": "Generally two years from the date of cause of action under Section 69.",
    "deterministic": false,
    "source": "llm_advisory",
    "expiry_date": null,
    "is_barred": null,
    "days_remaining": null
  },
  "case_law_references": [
    {"case_name": "…", "note": "…", "status": "unverified", "ik_url": null, "court": null}
  ],
  "missing_information": ["Exact date of purchase not provided"],
  "model_used": "gemini/gemini-2.5-flash",
  "generation_warning": null,
  "created_at": "2026-08-17T12:00:00Z",
  "notice": "AI-generated legal research for advocate review. Not legal advice."
}
```

`GET .../analyses` returns a JSON array of the same object shape.

## 7. Error Responses

| Status | Cause |
|---|---|
| `422` | `question` fails validation (too short, empty, whitespace-only) — FastAPI's standard validation error body. |
| `401` | No/invalid auth token. |
| `404` | `matter_id` supplied but doesn't exist or isn't owned by the caller. |
| `400` | `matter_id` supplied but belongs to a matter whose `module != "consulting"`. |
| `502` | Every LLM provider in the failover chain failed (Gemini → Groq → SambaNova → Cerebras all exhausted). Detail includes the underlying error text; safe to show a generic "AI providers are temporarily unavailable, try again" message — never render the raw detail as-is without review. |

## 8. Matter Creation Behavior

The first `analyze` call for a new question **is** the intake step —
there is no separate "create matter" call for Consulting. The matter is
created via the existing, unmodified `matters.create_matter` function
(same row shape as `POST /api/matters`), so it behaves identically to
any other matter for listing/metadata purposes (`GET /api/matters`,
`GET /api/matters/{id}`).

## 9. Follow-up / Version Behavior

Supplying `matter_id` on a later `analyze` call creates a new
`consulting_analyses` row (`version_no` incremented) inside the **same**
matter — verified by test: two `/analyze` calls against the same
`matter_id` produce version 1 and version 2, and exactly one `matters`
row exists throughout. The service also threads the last 3 prior
question/answer turns as conversation context into the LLM call, so a
follow-up is answered with awareness of what was already discussed, not
as an unrelated fresh query.

## 10. PII Masking Behavior

Every question passes through the existing PII Masker
(`SupabaseMaskStore` + `mask_text`/`unmask_text`) before it ever reaches
an external LLM provider — identical mechanism and per-matter mask map
(`pii_masks` table) as every other module. `party_names`/`addresses` are
optional additional hints; automatic PAN/Aadhaar/phone/email/name
detection always runs regardless. No second masking engine was
introduced.

## 11. RAG Behavior

Every analysis runs `hybrid_retrieve()` (unchanged) against the existing
shared `statute_chunks` corpus before calling the LLM, and includes the
retrieved context in the prompt. No new corpus, no module-specific
retriever. If a question falls outside the existing corpus,
`applicable_law` legitimately comes back sparse or empty — this is
correct behavior (refusing to fabricate a statute), not a bug. **Do not
add fallback/placeholder statute text on the frontend to paper over an
empty list.**

## 12. Citation Verification Behavior

Every `case_law_references` entry the model proposes is run through the
existing `verify_citation()` (bounded to 5 per request, same bound as
Litigation) before being returned. `status` is always the verifier's
real, independently-checked result — **never** the model's raw claim.
The model cannot mark its own proposed case as verified; verification
only ever happens server-side, after generation, via the same Indian
Kanoon-backed Citation Verifier every other module uses.

## 13. Grounded vs. Deterministic Fields — render these differently

- **`applicable_law[].grounded`**: `true` only if the (act, section_no)
  pair actually appeared in the statute corpus the RAG retriever found
  for this question. `false` means the model claimed it but it is **not
  confirmed against the corpus** — render visually distinct (the same
  "unverified" treatment used for citations), never with equal
  trustworthiness to a grounded entry.
- **`correct_forum.deterministic` / `limitation_period.deterministic`**:
  `true` only when you supplied `forum`/`limitation` in the request
  (i.e., the Forum Advisor / Limitation Calculator actually ran). `false`
  means it is the LLM's own advisory opinion — render with a visibly
  weaker confidence treatment (e.g. "AI estimate — run the Forum Advisor
  / Limitation Calculator for a definite answer"). Either field may be
  `null` entirely.
- **`case_law_references[].status`**: `"verified"` → safe to render as a
  live hyperlink to `ik_url`. `"unverified"` → **must render grey, no
  link**, labeled `"Unverified — confirm manually (may exist only on
  SCC/Manupatra)"` — the Citation Gate hard rule, identical requirement
  to Litigation. Never let a missing status check silently upgrade
  `"unverified"` to a clickable link.

## 14. Loading / Error Expectations

`POST /api/consulting/analyze` is synchronous — RAG retrieval, an LLM
call (with the gateway's own multi-provider failover and one JSON-repair
retry), and up to 5 citation verification calls all happen in the same
request. Expect several seconds, comparable to Litigation's
`POST /api/matters/{id}/case-analysis` — show a loading state, not a
spinner timeout under ~15s. There is no async/job-polling variant in
Phase 1. On `generation_warning != null`, `applicable_law`,
`remedies_available`, and `case_law_references` are all empty arrays
(never fabricated placeholder content) — show the warning text and offer
a retry (a fresh `analyze` call creates the next version), rather than
treating the empty arrays as "no applicable law found."

## 15. Frontend Rendering Rules (summary)

1. Never render a `case_law_references` entry as a link unless
   `status === "verified"`.
2. Never present `applicable_law[].grounded === false` with the same
   visual weight as `true`.
3. Never present `deterministic === false` forum/limitation with the
   same visual weight as `deterministic === true`.
4. Always show the `notice` disclaimer text.
5. Always show `missing_information` prominently — it's the mechanism
   surfacing "ask a follow-up before relying on this," not a minor
   footnote.

## 16. What Frontend MUST NOT Assume

- Do **not** call `POST /api/matters/{id}/messages` expecting structured
  Consulting output — it already technically routes Consulting matters
  through the `consulting_analyst` task type (via `MODULE_TASK_TYPE`),
  but it is plain free-text chat with no RAG grounding, no citation
  verification, no structured fields. It remains available as a
  lightweight "chat about this matter" surface if wanted, but it is not
  a substitute for `/analyze`.
- Do **not** assume a `consulting_case`/`consulting_matter` entity
  exists — use `matters` with `module === "consulting"`.
- Do **not** assume the live database currently has the
  `consulting_analyses` table — see §18, migration not yet applied.
- Do **not** assume `correct_forum`/`limitation_period` are ever
  authoritative unless `deterministic === true`.

## 17. Known Limitations (Phase 1)

- **No curated legal source data was added.** The RAG retriever answers
  only from the existing shared 12-act corpus. An out-of-corpus question
  legitimately returns sparse/empty `applicable_law`.
- **No separate LLM-based "query validator" classification step**
  (`{is_legal_matter, domain, urgency, missing_facts}`, as sketched in
  `10_Architecture/AI_Architecture.md`) was implemented as a distinct API
  call — its intent is served by the single analysis call's own
  `missing_information` field.
- **No document/strategy-brief generation.** Phase 1 is analysis only;
  the litigation-support "strategy brief" half of Module 4 (arguments,
  counter-arguments, authorities for a matter argued by other counsel)
  is not built — a Phase 2 gap, not silently dropped.

## 18. E2E Verification Status — read this before integrating

**Migration `0020_consulting_backend.sql` has been applied to the live
Supabase project (manually, via the SQL Editor, 18 August 2026) and full
live verification has since been completed and passed — 18/18 checks,
against the real production database, using real authenticated Supabase
users and real HTTP-equivalent requests through the actual FastAPI app
(no mocks, no dependency overrides).**

**Live schema** (PostgREST introspection): `consulting_analyses` exists;
all 15 expected columns present; `matter_id`/`version_no`/`question`
confirmed `NOT NULL` as migration 0020 specifies.

**Live RLS**: confirmed both behaviorally and directly.
- Enabled — an anon-key client sees 0 rows.
- Owner (real authenticated user, real JWT) can `SELECT` and `INSERT`
  their own analysis rows — proven both via the real
  `POST /api/consulting/analyze` / `GET .../analyses` endpoints AND via a
  direct `consulting_analyses` table query using that user's own
  RLS-scoped client.
- A second real authenticated user cannot see the first user's analysis
  rows — proven at **both** layers: the API returns `404` for
  `GET .../analyses` and for a follow-up `POST /analyze` against the
  first user's `matter_id` (app-layer `_get_matter_or_404`), **and** a
  direct `consulting_analyses` table query as the second user returns 0
  rows for that matter (the Postgres RLS policy itself, not just app
  logic) — this closes the exact gap the original implementation report
  flagged as unit-test-unprovable.
- An anon-key client also sees 0 rows for the specific matter tested.

**Live API**: `POST /api/consulting/analyze` (new matter → version 1;
follow-up with `matter_id` → version 2, same matter) and
`GET /api/consulting/matters/{id}/analyses` (2 versions returned,
most-recent-first) both verified against the live database with a real
LLM call actually executing (Gemini's top two pinned models failed live —
one rate-limited, one retired server-side — and the gateway's own
failover correctly degraded to `gemini-2.5-flash-lite`, which succeeded;
this is a pre-existing, unrelated Gemini model-pool staleness issue,
**not a Consulting defect**, and was not touched — flagged for a
separate fix outside this task's scope).

**E2E test data**: created via the project's established throwaway-account
convention (`e2e-test@vidhidesk.local`, plus a second throwaway account
`e2e-test-2@vidhidesk.local` for the cross-user check, both left in
place permanently per the existing convention — see
`api/e2e/test_no_auto_pdf_download.py`), with every created row's title
prefixed `[TEST] ` per `docs/20_Engineering/Lessons_Learned.md`'s process
rule. Exactly one matter and two `consulting_analyses` rows were created;
both were deleted by exact id (ownership-verified, fail-closed) in
cleanup, and cleanup itself was verified: a post-delete query confirmed
both the matter and its cascade-deleted `consulting_analyses` rows are
gone. No fabricated or leftover data remains in production from this
verification pass.

**Consulting backend is now genuinely end-to-end verified**, not just
unit-tested against a fake database. Frontend integration can proceed
against the live API with no known blockers.
