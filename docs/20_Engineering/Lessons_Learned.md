> **Title:** Lessons Learned
> **Version:** Living document (append-only)
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents building templates/skeletons
> **Last Updated:** 2 August 2026
> **Canonical Reference:** Yes, for known non-obvious engineering traps
> **Supersedes:** N/A
> **Related Documents:** [`20_Engineering/Repository_Standards.md`](Repository_Standards.md), [`30_Implementation/Backlog.md`](../30_Implementation/Backlog.md)

---

# Lessons Learned

Durable, file-based record of non-obvious traps hit during development —
the kind of thing that would otherwise get rediscovered the hard way on
the next template/feature. Add an entry here whenever something silently
does the wrong thing (no error, no crash — just wrong output) and the fix
isn't discoverable from the library's own error messages.

## docxtpl: Subdocument content requires the `{{p name}}` paragraph tag, not `{{ name }}`

**Symptom:** A docxtpl skeleton with `{{ clauses_subdoc }}` on its own
paragraph rendered successfully (no error, no exception) but the merged
clause content was completely missing from the output `.docx` — the
document jumped straight from the party block to the signature block.

**Cause:** A `Subdocument` (`tpl.new_subdoc()`) holds raw multi-paragraph
Word XML (`<w:p>` elements). The plain `{{ name }}` tag only substitutes
*text content inside the existing run* — it has no way to splice in
sibling paragraphs, so the Subdocument's XML gets dropped as invalid
content inside a `<w:t>` element rather than raising a visible error.
docxtpl has a **separate, paragraph-level tag syntax for this exact
case**: `{{p name}}` (note: no space after `{{`, immediately followed by
`p`, then a space, then the variable name) tells docxtpl to replace the
*entire enclosing paragraph* with the Subdocument's content, which is
what actually merges the XML in correctly.

```python
# Wrong — silently renders empty, no exception:
doc.add_paragraph().add_run("{{ clauses_subdoc }}")

# Right:
doc.add_paragraph().add_run("{{p clauses_subdoc}}")
```

**Where this matters going forward:** every Contracts template skeleton
(NDA built in Sprint 2 Deliverable 1; templates 2-10 to follow) uses the
same "merged, ordered, variant-filtered clause list as one Subdocument"
pattern (see `app/services/contracts.py::generate_draft`). Any new
skeleton built with `api/scripts/build_nda_skeleton.py` as a reference —
or any future template's build script — must use `{{p ...}}` for its
clause-content placeholder, not `{{ ... }}`. The same rule applies to
docxtpl's `RichText` objects (used for inline rich-formatted text, as
opposed to whole extra paragraphs) — those use their own `{{r name}}`
run-level tag for the same reason; plain `{{ name }}` only ever works
for a real string value being substituted as plain text.

**How it was caught:** a test asserted specific clause text appeared in
the rendered `.docx` (`tests/test_contracts.py::test_generate_draft_renders_real_docx_skeleton`)
and failed with the clause text simply absent — no traceback pointing at
the cause. Confirmed via a minimal standalone repro (build a two-paragraph
skeleton, render a Subdocument into it, inspect the output with
`python-docx`) before and after switching the tag syntax.

## Contract skeletons: use the `an_or_a` filter for "a/an {{ variable }}", never hardcode the article

**Symptom:** NDA's live E2E run produced "Ramesh Kumar, **a** Individual
having its registered address..." — grammatically wrong every time the
entity type starts with a vowel sound, not an edge case (of the NDA
schema's 6 entity-type options, "Individual" alone guarantees this fires
constantly).

**Cause:** the skeleton hardcoded the article: `"a {{ party_a_entity_type }}"`.
Jinja has no built-in a/an logic, and English's a/an rule depends on the
*sound* the following word starts with, not just its spelling — acronyms
like "LLP" are read "el-el-pee" (vowel sound) despite starting with a
consonant letter.

**Fix:** a shared Jinja filter, registered once and available to every
template's docx rendering (not per-template code):

```python
# app/services/contracts.py
def _an_or_a(word: str) -> str:
    first = word.strip().split()[0]
    if first.upper() in _VOWEL_SOUND_ACRONYMS:  # LLP, MSME, HUF, ...
        return "an"
    return "an" if first[0].lower() in "aeiou" else "a"

_docx_jinja_env = jinja2.Environment()
_docx_jinja_env.filters["an_or_a"] = _an_or_a
```
```
{{ party_a_entity_type | an_or_a }} {{ party_a_entity_type }}
```
`generate_draft()` passes `jinja_env=_docx_jinja_env` to every `tpl.render()`
call, so this is available to *every* template's skeleton automatically —
nothing to wire up per template.

**Where this matters going forward:** any skeleton (templates 2-10)
writing "a/an {{ some_variable }}" against a field whose value varies
(entity types, categories, anything user-selected from an open-ended
list) must use `| an_or_a`, not a hardcoded article. Same
cheap-to-fix-once-vs-painful-across-ten-templates tradeoff as the
`{{p }}` entry above — both are one-line fixes in the shared engine that
every future template inherits for free, versus a bug that would
otherwise get rediscovered and patched separately in each new skeleton.

## Clause numbers are auto-assigned; sub-numbers inside a clause are not

**Context (migration 0008, Sprint 2 Deliverable 2 prep):** a clause's
outer number ("3. Confidentiality Obligations") is no longer hardcoded in
its `source_text` — `generate_draft()` derives it at assembly time from
each clause's `heading` field, counting only clauses that survive
`applicable_condition` filtering. This is what makes a conditionally
*excluded* clause (Service Agreement's optional SLA clause) correctly
shift every later clause's number, instead of leaving a gap or a stale
hardcoded value.

**What this does NOT cover:** numbering *inside* a clause's own body —
NDA's Definitions clause has hand-authored "1.1", "1.2", "1.3"
sub-points; Miscellaneous has "10.1"–"10.6". Those literal sub-numbers
assume the clause they belong to lands on a specific outer number (1 and
10 respectively). That assumption only holds because, in NDA specifically,
no conditionally-excludable clause can ever land *before* Definitions or
*after* Miscellaneous — so their outer numbers are fixed regardless of
which variant is chosen.

**Before reusing a clause's body across templates, or adding a
conditional clause near one with internal sub-numbers:** check whether
the assumption above still holds. If a future template puts a
conditionally-excluded clause *before* a clause with hardcoded
sub-numbers, those sub-numbers will silently go stale (still says "1.1"
even though the clause is now actually numbered 2). No test currently
catches this generically — it would need a per-template check that a
clause's internal sub-numbers match its assembled outer number.

## Checkbox fields need explicit flex layout, not the default stacked Label-then-input

**Symptom:** found live in Service Agreement's E2E (2026-08-01) —
"Include Service Level Terms?" and "Include Arbitration Clause?" rendered
with the checkbox squished directly against the label text, no visible
gap, on `IntakeForm`'s generic `FieldRow` (`<Label>` then the control,
wrapped in `space-y-2`).

**Cause:** `space-y-2` (Tailwind's `> * + *` margin-top) relies on
margin-top actually being respected between the two elements. `<Label>`
(a `<label>` tag) and `<input type="checkbox">` are both inline-level —
inline elements don't respect vertical margin in normal flow, so the
nominal spacing silently had no visual effect. Every other field type
(text/select/textarea/date) works fine with the same `space-y-2` pattern
because their controls (`<Input>`, `<Select>`, `<Textarea>`) render as
block-level elements, where margin-top *is* respected — the bug was
specific to the one field type that doesn't follow that layout.

**Fix:** boolean fields get their own branch in `FieldRow`
(`web/src/components/intake-form.tsx`) — checkbox and label side by side
in an explicit `flex items-center gap-2` row, not stacked. This also
happens to be the more conventional checkbox UX ("[ ] Label", not
"Label" / newline / "[ ]"), so the fix and the idiomatic pattern are the
same change.

**Where this matters going forward:** any new field *type* added to
`IntakeField` (a future `"currency"` or `"multiselect"`, say) should be
checked for the same inline-vs-block layout assumption before assuming
`FieldRow`'s default stacked layout works for it — it's a real, silent
failure mode (no console error, no build warning), not just a style
nitpick.

## Process rule: always run live browser E2E on the seeded template after any schema/clause change, before marking a batch done

**Why this is a rule, not a suggestion:** four distinct silent bugs in
Sprint 2 alone passed the full backend unit-test suite and were only
caught by an actual browser click-through against the live-seeded
template:

1. StrictUndefined crash on a conditionally-hidden field (NDA) —
   `form_data` from the real frontend simply omits a key the schema
   declares; every hand-constructed test fixture had that key.
2. "Fixed Fee" masked into a `PARTY_x` placeholder, silently breaking a
   `fixed_boilerplate` clause's own `{% if fee_structure == 'Fixed Fee' %}`
   comparison (Service Agreement) — no test exercised masking against a
   real `select` field value.
3. Truncated deliverable descriptions from an embedded newline inside a
   `textarea` value fragmenting a docx paragraph mid-sentence (Service
   Agreement) — no test fixture had ever put a `\n` inside a text field.
4. An orphaned `template_clauses` row surviving a clause_key rename and
   silently re-rendering as a duplicate clause in every new draft
   (Service Agreement) — a pure DB-state bug; the FakeDB in
   `tests/test_contracts.py` always starts empty, so this class of bug
   is structurally invisible to the unit suite no matter how the
   fixtures are written.

The common thread: unit tests validate the *code*, driven by
hand-constructed input. All four bugs lived in the gap between "code is
correct in isolation" and "real state (real frontend behavior, real
schema shapes, real DB history) produces the input the code actually
sees." Schema-driven unit tests closed part of that gap (see
`_load_service_agreement_fixtures`/`_load_nda_fixtures` in
`test_contracts.py`, which load the real seed script + real
`.schema.json` instead of hand-rolled fixtures) — but bug 4 shows even
that isn't sufficient, because it's a *live DB state* bug, not a code or
schema-shape bug.

**Rule:** after any change to a template's schema JSON or its seed
script's `CLAUSES`, re-run that seed script against the live DB, then
drive at least one full intake-to-download run through a real browser
before considering the change (or the batch containing it) done — not
just "tests pass." This is the only check that observes the actual
composed output (rendered docx text, clause count, paragraph
boundaries) the way Nitesh will. Apply this for the remainder of Sprint
2 without needing to be told each time — routine, not exceptional.

## Design pattern: real intake field vs. `[ADVOCATE REVIEW: ...]` clause-review flag

When a clause needs to vary per matter, choose the mechanism by whether
the *range* of variation is enumerable:

- **Real intake field** (a `select` or short `text` field driving
  `applicable_condition`-gated clause variants, or a straight
  substitution) — when the value can be captured as a select or short
  text field without losing meaning. Example: `confidentiality_direction`
  (mutual / one-way-from-Client / one-way-from-Provider) — three
  well-defined states, each with materially different clause text.
- **`[ADVOCATE REVIEW: ...]` bracketed flag inside the drafted clause**
  — when the value is inherently narrative or deal-specific enough that
  forcing it into a field would either lose meaning or require an
  unbounded number of fields. Example: arbitration institution/rules
  (ad hoc vs. institutional — MCIA, SIAC, DIAC — arbitrator count,
  language) — genuinely negotiated per deal, not a fixed enum worth
  building UI for.

**The dividing line:** "can this be a select/short-text field without
losing meaning?" — yes → intake field; no → flag. Don't default to
flagging everything (it under-serves matters where the answer really is
one of a handful of fixed options) or fielding everything (it grows the
intake form for genuinely one-off, narrative decisions the advocate
should just make directly in the drafted text).

## Design pattern: `applicable_condition`-per-variant is the standard mechanism for "same logical clause, different content by variant"

NDA's `confidentiality_obligations_mutual` / `confidentiality_obligations_one_way`
(migration 0008) and Service Agreement's `confidentiality_mutual` /
`confidentiality_one_way_from_client` / `confidentiality_one_way_from_provider`
(Sprint 2 design gap fix) are the same pattern: several `template_clauses`
rows share one `display_order` and `heading`, each gated by a distinct
`applicable_condition` value on the same intake field, so exactly one
survives `_applicable_clauses()` filtering for any given matter.

**Reuse this whenever a future template has "one conceptual clause, but
its content genuinely differs by a matter-level choice"** — Employment's
probation / no-probation, Lease's furnished / unfurnished, and similar
are expected instances of the exact same shape. Don't reach for Jinja
`{% if %}` branching *within* a single clause's `source_text` once the
branches diverge enough to need materially different legal language (as
opposed to swapping a name or a number) — separate clause rows keep each
variant's text independently reviewable in the clause-review UI, which a
single branching mega-prompt does not.

**Reminder when adding a new variant set this way:** renaming or
splitting a `clause_key` this way is exactly the operation that produced
the orphaned-row bug above — always re-run the seed script (which now
prunes safely-orphaned rows automatically, see
`_prune_orphaned_clauses` in both `scripts/seed_*_template.py` files)
and verify live per the process rule above, not just unit tests.

## Process rule: prefix test-matter titles with `[TEST]`, and re-seeding a clause does not clear a prior review

**Context (2026-08-02 audit sweep):** the live-E2E discipline established
above is doing real work, but it also writes real rows into
`matters`/`draft_versions`/`clause_reviews` against the live Supabase
project — the same DB Nitesh's actual review workflow runs against.
Two follow-on problems surfaced during a routine audit sweep of that
accumulated state:

1. **Finding test rows required filtering by the throwaway auth user's
   email** (`e2e-test@vidhidesk.local`) joined through `matters.user_id`
   — there was no cheaper signal (like a title prefix) to filter on.
   This works, but only because every E2E run so far has consistently
   used that one throwaway account; it doesn't scale to "which of
   Nitesh's own matters did I accidentally touch," and requires a
   privileged auth lookup just to ask "is this a test row."

2. **A more serious finding:** two `clause_reviews` rows on NDA's
   `recitals`/`definitions` clauses, decision `keep`, dated
   2026-08-01T15:35 — from an early clause-review-screen verification
   pass, *before* the recitals party-names bug was found and fixed later
   that same day. `template_clauses.review_status` still showed `kept`
   for `recitals` right up until this audit, because
   `seed_nda_template.py`'s upsert only ever writes
   `source_text`/`current_text`/etc. — it has no way to know a
   clause's *content* changed underneath a review that already happened,
   so it never touches `review_status`/`reviewed_at`. A clause can
   silently carry a stale "reviewed and kept" badge against text that
   isn't what was actually reviewed. Both rows were deleted and the two
   `template_clauses` rows reset to `unreviewed`/`null` after confirming
   (a) the timestamp pre-dates the content fix and (b) zero
   `draft_clause_fills` reference them (fixed_boilerplate-adjacent check
   — `recitals` is `llm_fillable`, so this needed an explicit check, not
   an assumption).

**Going forward:**
- **Give every matter created by a live E2E run a title prefixed
  `[TEST] `** (e.g. `[TEST] Consultancy Retainer, mutual confidentiality`).
  Future cleanup/audit queries can then filter on `matters.title like
  '[TEST]%'` directly — cheaper and more robust than joining through a
  specific auth user, and it stays correct even if a second throwaway
  account is ever added. Apply this to `api/e2e/test_no_auto_pdf_download.py`
  and any ad hoc verification script.
- **After re-seeding a template whose change rewrites a clause a human
  has already reviewed, check whether that clause's `review_status`
  should be reset.** The seed scripts don't do this automatically (and
  arguably shouldn't without a human decision — a wording tweak that
  doesn't change meaning is different from the kind of substantive
  rewrite the recitals fix was). No code fix applied here; noting it as
  a manual check to perform, not (yet) an automated one, since getting
  the automatic version wrong (over-invalidating trivial edits) has its
  own cost.
