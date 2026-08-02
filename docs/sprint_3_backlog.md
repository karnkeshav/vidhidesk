# Sprint 3 Backlog

Tickets accumulated during Sprint 1 (Statute RAG + Citation Verifier)
and Sprint 2 (Contracts template engine, Batches 1-3) that were
deliberately deferred rather than fixed in-flight — captured here so
Sprint 3 kickoff starts from an honest list, not a rediscovery of gaps.
Each entry names where it was surfaced; see that source for full context
before starting the work.

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
*Source: observed across Batches 1-3 (Service Agreement, Consultancy, MoU).*
