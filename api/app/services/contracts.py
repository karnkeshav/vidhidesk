"""Contracts template engine (Sprint 2, Deliverable 1 — NDA end-to-end).

Pipeline: JSON-schema intake data -> LLM fills the llm_fillable clauses
(through the same PII-masked gateway path matters.py already uses,
CLAUDE.md Decision 4) -> docxtpl renders the fixed skeleton with the
resulting clause set -> draft_versions + draft_clause_fills record the
result for audit (CLAUDE.md Hard Rule 4).

Structure and boilerplate never come from the LLM (Hard Rule 2): only
template_clauses rows marked clause_type='llm_fillable' ever reach
llm_gateway.generate(); 'fixed_boilerplate' clauses are copied through
as-is from the reviewed template.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import jinja2
from docxtpl import DocxTemplate

from app.db import service_client
from app.services.llm_gateway import GenerationResult, generate
from app.services.pii_mask import SupabaseMaskStore, mask_text

logger = logging.getLogger("vidhidesk.contracts")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DRAFTS_DIR = Path(__file__).resolve().parent.parent.parent / "generated_drafts"

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

DISCLAIMER = "AI-generated draft for advocate review. Not legal advice."

# --- an_or_a filter (TICKET-3) ----------------------------------------------
# A docx skeleton writing "a {{ party_a_entity_type }}" reads "a Individual"
# for any vowel-leading entity type — wrong every time it happens, not an
# edge case (Individual, LLP... wait LLP is consonant-sounding "el-el-pee"
# but starts with a letter that's read as a vowel sound; see the acronym
# note below). One filter fixes it for every template that needs it, not
# just NDA. See docs/lessons_learned.md.
_VOWEL_SOUND_ACRONYMS = {"LLP", "MSME", "HUF"}  # read as "el-el-pee", "em-es-em-ee", "aitch-you-eff" — vowel-leading sound despite consonant spelling


def _an_or_a(word: str) -> str:
    if not word:
        return "a"
    first = word.strip().split()[0]
    if first.upper() in _VOWEL_SOUND_ACRONYMS:
        return "an"
    return "an" if first[0].lower() in "aeiou" else "a"


_docx_jinja_env = jinja2.Environment()
_docx_jinja_env.filters["an_or_a"] = _an_or_a


@dataclass
class ClauseFillRecord:
    template_clause_id: str
    clause_key: str
    generated_text: str
    prompt: str
    model_used: str


@dataclass
class DraftResult:
    draft_version_id: str
    version_no: int
    docx_path: str
    clause_fills: list[ClauseFillRecord]
    # The fully assembled, fully rendered clause text (numbered, Jinja-
    # substituted) — the server-side source of truth for the frontend's
    # plain-text preview, so the browser never has to reconstruct it
    # (and inevitably get it wrong once a fixed_boilerplate clause has
    # {% for %}/{{ }} tags in it, which the client can't render).
    full_text: str


def _variant_role_labels(nda_variant: str, party_a_role: str | None) -> tuple[str, str]:
    if nda_variant == "mutual":
        label = "Disclosing Party and Receiving Party"
        return label, label
    # one_way: party_a_role is 'disclosing' or 'receiving'; party B is the counterpart.
    if party_a_role == "disclosing":
        return "Disclosing Party", "Receiving Party"
    return "Receiving Party", "Disclosing Party"


def _with_schema_defaults(form_data: dict, schema: dict) -> dict:
    """Fill in `""` for any schema-declared field the caller didn't submit
    (e.g. an optional field the user never touched, or one hidden by a
    `condition` that never became true — a real Sprint 2 E2E bug: the NDA
    form's arbitration_seat field is conditionally hidden when arbitration
    is unchecked, so it's simply absent from form_data, and the AND-strict
    `_jinja_env` (StrictUndefined) raised on it inside the governing-law
    clause prompt).

    Deliberately still uses StrictUndefined at render time, not a lenient
    Undefined — a Jinja template referencing a key that isn't in the
    schema AT ALL (a genuine typo) should still raise, not silently
    render blank. This only pre-fills keys the schema itself declares.

    Recursive for `type: "list"` fields (Sprint 2 Deliverable 2, generic
    list/repeater field): a missing list field defaults to `[]`; each
    submitted item is itself defaulted against the field's `item_schema`
    (a plain field list, same shape as the top-level `fields` array) by
    calling this same function on it — a StrictUndefined crash on a
    conditionally-empty or never-touched per-item field (e.g. an optional
    `notes` sub-field left blank on one deliverable but not another) is
    the exact same bug class as the top-level one, one level down.
    `schema` accepts either a full schema (`{"fields": [...]}`) or a bare
    field list wrapped the same way, so item-level recursion doesn't need
    a second code path.
    """
    result = dict(form_data)
    for field in schema.get("fields", []):
        key = field["key"]
        if field.get("type") == "list":
            items = result.get(key) or []
            item_schema = {"fields": field.get("item_schema", [])}
            result[key] = [_with_schema_defaults(item, item_schema) for item in items]
        elif key not in result:
            result[key] = field.get("default", "")
    return result


_FREE_TEXT_FIELD_TYPES = {"text", "textarea"}
_EMBEDDED_NEWLINE_RE = re.compile(r"\s*[\r\n]+\s*")


def _normalize_free_text(form_data: dict, schema: dict) -> dict:
    """Collapse embedded newlines out of user-typed text/textarea values
    before they're interpolated into a clause's Jinja source_text.

    Bug found live 2026-08-01 (Sprint 2, Service Agreement docx
    click-through): a deliverable description came out truncated
    mid-word in the rendered docx. Root cause — `deliverables[].
    description` is a `type: "textarea"` field (a real multi-row
    control, see intake-form.tsx's `rows={3}`), so a user pressing Enter,
    or pasting text copied from a justified PDF/Word paragraph with
    hyphenated line wraps, embeds a literal "\n" inside a single field's
    value. Every clause's source_text assembles its rendered text as one
    flat run of prose (or one bullet line inside a `{% for %}` loop), and
    `generate_draft`'s docx-assembly step later does
    `rendered_clause_text.split("\n")` to turn the *template author's*
    intentional paragraph breaks (NDA's "1.1 ... \n1.2 ..." Definitions
    clause, for instance) into separate docx paragraphs. That split can't
    distinguish "the template's own structural newline" from "a newline
    that happened to be inside a client's answer" — so an embedded
    newline in a field value silently fragments that value across two
    docx paragraphs mid-sentence, with no bullet/prefix on the orphaned
    continuation. Fix: normalize embedded newlines out of every
    text/textarea value (collapsing to a single space) before it's ever
    interpolated into a clause's Jinja template — applied early in
    `generate_draft`, so masking, entity detection, and rendering all see
    already-normalized text. Same recursive schema-aware shape as
    `_mask_form_data`/`_with_schema_defaults`; deliberately not scoped to
    `deliverables` alone, since every other text/textarea field
    (`purpose`, `ip_carveout_notes`, `sla_credit_terms`, ...) is
    interpolated the exact same way and is equally exposed.
    """
    result = dict(form_data)
    for field in schema.get("fields", []):
        key = field["key"]
        if key not in result:
            continue
        if field.get("type") == "list":
            item_schema = {"fields": field.get("item_schema", [])}
            result[key] = [
                _normalize_free_text(item, item_schema) if isinstance(item, dict) else item
                for item in result[key]
            ]
        elif field.get("type") in _FREE_TEXT_FIELD_TYPES and isinstance(result[key], str):
            result[key] = _EMBEDDED_NEWLINE_RE.sub(" ", result[key]).strip()
    return result


def _mask_form_data(form_data: dict, schema: dict, mask_map, entities) -> dict:
    """TICKET-1's field-level pre-masking (see mask_text's docstring), made
    schema-aware — a real bug found building Service Agreement: masking
    *every* string value indiscriminately (the original TICKET-1 fix)
    also masked `select` field values like "Fixed Fee", and the
    Title-Case-run heuristic false-positived on it exactly like it did on
    "Governing Law" — "Fixed Fee" became a PARTY_x placeholder, which
    silently broke a fixed_boilerplate clause's own
    `{% if fee_structure == 'Fixed Fee' %}` comparison (masked_form_data's
    value could never equal the literal string in the template, so no
    branch matched, and the clause rendered blank with no error).

    Fix: only mask `text`/`textarea` fields — genuine free text a client
    or advocate typed, where incidental PII is plausible. `select`/
    `boolean`/`date` values are controlled vocabulary the schema itself
    defines; they're never PII, and callers (including this module's own
    Jinja conditionals) rely on comparing them by exact value. Same
    recursive shape as `_with_schema_defaults` for `type: "list"` fields.
    """
    result = dict(form_data)
    for field in schema.get("fields", []):
        key = field["key"]
        if key not in result:
            continue
        if field.get("type") == "list":
            item_schema = {"fields": field.get("item_schema", [])}
            result[key] = [
                _mask_form_data(item, item_schema, mask_map, entities) if isinstance(item, dict) else item
                for item in result[key]
            ]
        elif field.get("type") in _FREE_TEXT_FIELD_TYPES and isinstance(result[key], str):
            result[key] = mask_text(result[key], mask_map, entities)
    return result


def _mask_value_recursive(value, mask_map, entities):
    """Same TICKET-1 field-level pre-masking as top-level scalar fields,
    extended into `type: "list"` field values (a list of item dicts —
    e.g. one deliverable's free-text description could just as easily
    carry incidental PII as the top-level `purpose` field can).

    Not schema-aware — only safe for values already known to be free
    text (e.g. `amendment_note`, which is never a schema field). For
    schema-declared form_data, use `_mask_form_data` instead (see its
    docstring for why this distinction matters)."""
    if isinstance(value, str):
        return mask_text(value, mask_map, entities)
    if isinstance(value, list):
        return [
            {k: _mask_value_recursive(v, mask_map, entities) for k, v in item.items()}
            if isinstance(item, dict)
            else _mask_value_recursive(item, mask_map, entities)
            for item in value
        ]
    return value


def _clause_is_applicable(clause: dict, form_data: dict) -> bool:
    """Generic clause-inclusion condition (Sprint 2 Deliverable 2), same
    {field, equals}/{field, not_equals} shape as the frontend's per-field
    visibility condition — deliberately, so "when is this clause
    included" and "when is this form field shown" are one mental model,
    not two. Replaces NDA's one-off applicable_variant column (which only
    ever compared against a hardcoded "nda_variant" key)."""
    condition = clause.get("applicable_condition")
    if not condition:
        return True
    actual = form_data.get(condition["field"])
    if "equals" in condition:
        return actual == condition["equals"]
    if "not_equals" in condition:
        return actual != condition["not_equals"]
    return True


def _applicable_clauses(all_clauses: list[dict], form_data: dict) -> list[dict]:
    return [c for c in all_clauses if _clause_is_applicable(c, form_data)]


def _entities_from_form(form_data: dict, matter: dict | None) -> list[tuple[str, str]]:
    entities: list[tuple[str, str]] = []
    for key in ("party_a_name", "party_b_name"):
        if form_data.get(key):
            entities.append(("PARTY", form_data[key]))
    for key in ("party_a_address", "party_b_address"):
        if form_data.get(key):
            entities.append(("ADDR", form_data[key]))
    if matter and matter.get("client_name"):
        entities.append(("PARTY", matter["client_name"]))
    return entities


def _next_version_no(matter_id: str, db) -> int:
    rows = (
        db.table("draft_versions")
        .select("version_no")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (rows[0]["version_no"] + 1) if rows else 1


def generate_draft(
    matter_id: str, template_id: str, form_data: dict, amendment_note: str | None = None, db=None
) -> DraftResult:
    """Generate a new draft version for `matter_id` from `template_id`.

    Always creates a *new* draft_versions row (AC-2.3: amendment produces a
    new version without losing prior ones) — calling this again with
    updated form_data for the same matter is the amendment loop; nothing
    here overwrites an existing version.

    `amendment_note` is free text from the chat-style amendment pane (e.g.
    "reduce lock-in to 12 months", CLAUDE.md's own example). v1 of the
    amendment loop: rather than classifying which single clause a command
    targets (a separate, fragile NLP problem), the note is appended as
    extra instruction to *every* llm_fillable clause's prompt for this
    regeneration — each clause's own LLM call decides whether the note is
    relevant to it. Simple, safe (never silently drops the advocate's
    instruction), and reuses 100% of the existing per-clause pipeline.
    Clause-specific targeting is a reasonable future refinement, not a
    correctness requirement for this deliverable.
    """
    db = db if db is not None else service_client()

    template = db.table("templates").select("*").eq("id", template_id).execute().data
    if not template:
        raise ValueError(f"template {template_id} not found")
    template = template[0]
    form_data = _with_schema_defaults(form_data, template["schema_json"])
    form_data = _normalize_free_text(form_data, template["schema_json"])

    matter_rows = db.table("matters").select("*").eq("id", matter_id).execute().data
    matter = matter_rows[0] if matter_rows else None

    all_clauses = (
        db.table("template_clauses")
        .select("*")
        .eq("template_id", template_id)
        .order("display_order")
        .execute()
        .data
        or []
    )
    clauses = _applicable_clauses(all_clauses, form_data)

    mask_store = SupabaseMaskStore(db)
    mask_map = mask_store.load(matter_id)
    entities = _entities_from_form(form_data, matter)

    # TICKET-1 (Sprint 2 postmortem): mask every free-text user-supplied
    # value individually, with full auto-detection, BEFORE it's
    # interpolated into a clause prompt template — not the assembled
    # prompt afterward. That's what lets the outer generate() call below
    # safely pass auto_detect_names=False: every genuinely user-authored
    # string has already been through the full PAN/phone/name/company/
    # address pipeline by the time it reaches the LLM, so the only
    # unmasked text left is this module's own static instruction wording,
    # which is exactly what should never be scanned (see
    # pii_mask.mask_text's docstring for why — "NOW THEREFORE"/
    # "Governing Law" false-positived as person names when the whole
    # assembled prompt was scanned as one). Schema-aware (only text/
    # textarea fields, not select/boolean/date) — see _mask_form_data's
    # docstring for the Service Agreement bug that made this necessary:
    # masking a `select` value like "Fixed Fee" broke a fixed_boilerplate
    # clause's own Jinja `{% if fee_structure == 'Fixed Fee' %}` check.
    masked_form_data = _mask_form_data(form_data, template["schema_json"], mask_map, entities)
    masked_amendment_note = mask_text(amendment_note, mask_map, entities) if amendment_note else None

    clause_fills: list[ClauseFillRecord] = []
    final_clause_texts: list[str] = []

    # Assembly-time numbering (Sprint 2 Deliverable 2, migration 0008): a
    # clause's number is no longer hardcoded in its own text — it's derived
    # here, against the actual variant/condition-filtered `clauses` list,
    # so a conditionally-excluded clause (e.g. Service Agreement's SLA)
    # correctly shifts every later clause's number instead of leaving a
    # gap or a wrong hardcoded value. A clause with no `heading` (NDA's
    # recitals) gets no number and doesn't advance the counter.
    clause_number = 0

    for clause in clauses:
        if clause["clause_type"] == "fixed_boilerplate":
            # Jinja-rendered, not appended verbatim (Sprint 2 Deliverable 2):
            # a fixed_boilerplate clause never calls the LLM, but it can
            # still need per-matter substitution — a payment clause's fee
            # amount, a deliverables list via {% for %}. No LLM call means
            # no paraphrasing risk on numbers/verbatim list items, which is
            # exactly the point (see the Service Agreement field-
            # classification note: numeric/enumerable content is
            # structured+substituted, never llm_fillable). Safe for NDA's
            # existing tag-free boilerplate too — a template with no {{ }}
            # in it just renders back to itself unchanged.
            rendered = _jinja_env.from_string(clause["current_text"]).render(**masked_form_data)
        else:
            prompt = _jinja_env.from_string(clause["current_text"]).render(**masked_form_data)
            if masked_amendment_note:
                prompt += (
                    f"\n\n<user_amendment>\n"
                    f"Additional amendment instruction from the advocate for this "
                    f"revision (apply it only if relevant to this clause):\n"
                    f"{masked_amendment_note}\n"
                    f"</user_amendment>"
                )
            result: GenerationResult = generate(
                prompt,
                task_type="contract_drafter",
                mask_map=mask_map,
                entities=entities,
                auto_detect_names=False,
            )
            rendered = result.text
            clause_fills.append(
                ClauseFillRecord(
                    template_clause_id=clause["id"],
                    clause_key=clause["clause_key"],
                    generated_text=result.text,
                    prompt=result.masked_prompt,
                    model_used=result.model,
                )
            )

        heading = clause.get("heading")
        if heading:
            clause_number += 1
            rendered = f"{clause_number}. {heading}\n\n{rendered}"
        final_clause_texts.append(rendered)

    mask_store.save(mask_map)

    # NDA-specific derived context (mutual/one-way role-label swapping) —
    # gated on the specific "nda_variant" field name, not just "any
    # variant_field is declared": _variant_role_labels() hardcodes
    # mutual/one_way/Disclosing-Receiving semantics, so a future template
    # with a *different* variant concept (not this one) must not run
    # through it. A template with no variant concept at all (Service
    # Agreement: always asymmetric Provider/Client) skips this entirely.
    variant_field = template["schema_json"].get("variant_field")
    party_a_role_label, party_b_role_label = (
        _variant_role_labels(form_data.get("nda_variant", ""), form_data.get("party_a_role"))
        if variant_field == "nda_variant"
        else ("", "")
    )
    disclaimer_banner = DISCLAIMER
    if template.get("review_status") == "beta":
        disclaimer_banner = "BETA — PENDING CLAUSE REVIEW. " + disclaimer_banner

    tpl = DocxTemplate(str(REPO_ROOT / template["docx_path"]))
    # The skeleton's placeholder for this MUST be the docxtpl paragraph tag
    # {{p clauses_subdoc}}, not {{ clauses_subdoc }} — a Subdocument's raw
    # multi-paragraph XML silently disappears (no error) under the plain
    # tag. See docs/lessons_learned.md for the full story; any new template
    # skeleton reusing this pattern needs the same tag form.
    clauses_subdoc = tpl.new_subdoc()
    for text in final_clause_texts:
        for line in text.split("\n"):
            clauses_subdoc.add_paragraph(line)
        clauses_subdoc.add_paragraph("")

    # Base context is generic — every submitted form field is available to
    # any template's skeleton by its own schema key, not a hand-picked
    # subset. NDA-specific derived keys (role labels, the variant label)
    # are additions on top, scoped to templates that actually declare a
    # variant_field — a template with no variant concept just never gets
    # them, rather than every future template inheriting NDA's shape.
    context = {
        **form_data,
        "disclaimer_banner": disclaimer_banner,
        "party_a_role_label": party_a_role_label,
        "party_b_role_label": party_b_role_label,
        "clauses_subdoc": clauses_subdoc,
    }
    if variant_field == "nda_variant":
        context["nda_variant_label"] = "Mutual" if form_data.get("nda_variant") == "mutual" else "One-Way"
    tpl.render(context, jinja_env=_docx_jinja_env)

    version_no = _next_version_no(matter_id, db)
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    docx_path = DRAFTS_DIR / f"{matter_id}_v{version_no}.docx"
    tpl.save(str(docx_path))

    variant_suffix = f" ({form_data[variant_field]})" if variant_field else ""
    change_summary = (
        f"Amendment: {amendment_note}"
        if amendment_note
        else f"Generated from {template['name']}{variant_suffix}"
    )
    draft_row = (
        db.table("draft_versions")
        .insert(
            {
                "matter_id": matter_id,
                "template_id": template_id,
                "version_no": version_no,
                "docx_path": str(docx_path.relative_to(REPO_ROOT)),
                "change_summary": change_summary,
            }
        )
        .execute()
        .data[0]
    )

    if clause_fills:
        db.table("draft_clause_fills").insert(
            [
                {
                    "draft_version_id": draft_row["id"],
                    "template_clause_id": f.template_clause_id,
                    "generated_text": f.generated_text,
                    "prompt": f.prompt,
                    "model_used": f.model_used,
                    "retrieval_sources_json": None,
                }
                for f in clause_fills
            ]
        ).execute()

    return DraftResult(
        draft_version_id=draft_row["id"],
        version_no=version_no,
        docx_path=draft_row["docx_path"],
        clause_fills=clause_fills,
        full_text="\n\n".join(final_clause_texts),
    )


def list_drafts(matter_id: str, db=None) -> list[dict]:
    """Version history for a matter's drafts — newest first."""
    db = db if db is not None else service_client()
    return (
        db.table("draft_versions")
        .select("id,template_id,version_no,docx_path,change_summary,created_at")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .execute()
        .data
        or []
    )


def get_draft(draft_version_id: str, db=None) -> dict | None:
    db = db if db is not None else service_client()
    rows = db.table("draft_versions").select("*").eq("id", draft_version_id).execute().data
    return rows[0] if rows else None


LIBREOFFICE_TIMEOUT_SECONDS = 15


class PdfConversionUnavailable(Exception):
    """Raised when no LibreOffice (soffice) binary is on PATH. TRD §2/§3.4
    names LibreOffice headless as the sanctioned .docx -> .pdf path; this
    is NOT a fallback to a different converter, it's a clear signal the
    environment is missing the dependency (e.g. this dev sandbox has no
    passwordless sudo to install it — see docs/lessons_learned.md)."""


class PdfConversionTimeout(PdfConversionUnavailable):
    """Raised when LibreOffice PDF conversion exceeds the timeout limit."""


def convert_docx_to_pdf(docx_path: Path, timeout: int = LIBREOFFICE_TIMEOUT_SECONDS) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise PdfConversionUnavailable(
            "LibreOffice (soffice) is not installed in this environment — "
            "PDF export needs it (TRD §3.4). Docx export is unaffected."
        )
    pdf_path = docx_path.with_suffix(".pdf")
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("LibreOffice conversion timed out after %d seconds for %s", timeout, docx_path)
        raise PdfConversionTimeout(
            f"LibreOffice PDF conversion timed out after {timeout} seconds."
        ) from exc
    if not pdf_path.exists():
        raise PdfConversionUnavailable(f"soffice ran but did not produce {pdf_path}")
    return pdf_path


# --- Clause review (Project_Plan §6.2: keep / redraft / delete) ------------


def list_clauses(template_id: str, db=None) -> list[dict]:
    db = db if db is not None else service_client()
    return (
        db.table("template_clauses")
        .select("*")
        .eq("template_id", template_id)
        .order("display_order")
        .execute()
        .data
        or []
    )


VALID_DECISIONS = {"keep", "redraft", "delete"}


def review_clause(
    clause_id: str,
    decision: str,
    redraft_text: str | None = None,
    reviewer_notes: str | None = None,
    db=None,
) -> dict:
    """Record one keep/redraft/delete decision on a template clause and
    update its denormalized review_status/current_text in the same pass.
    If this was the last unreviewed clause on its template, the template
    flips from 'beta' to 'reviewed' (Project_Plan §6.4's 100%-by-gate
    target)."""
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {VALID_DECISIONS}, got {decision!r}")
    if decision == "redraft" and not redraft_text:
        raise ValueError("redraft_text is required when decision='redraft'")
    if decision == "delete" and not reviewer_notes:
        raise ValueError("reviewer_notes is required when decision='delete'")

    db = db if db is not None else service_client()

    clause_rows = db.table("template_clauses").select("*").eq("id", clause_id).execute().data
    if not clause_rows:
        raise ValueError(f"template_clause {clause_id} not found")
    clause = clause_rows[0]

    db.table("clause_reviews").insert(
        {
            "clause_id": clause_id,
            "decision": decision,
            "redraft_text": redraft_text,
            "reviewer_notes": reviewer_notes,
        }
    ).execute()

    new_status = {"keep": "kept", "redraft": "redrafted", "delete": "deleted"}[decision]
    new_current_text = redraft_text if decision == "redraft" else clause["current_text"]

    updated = (
        db.table("template_clauses")
        .update(
            {
                "review_status": new_status,
                "current_text": new_current_text,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", clause_id)
        .execute()
        .data[0]
    )

    siblings = (
        db.table("template_clauses")
        .select("review_status")
        .eq("template_id", clause["template_id"])
        .execute()
        .data
        or []
    )
    if siblings and all(s["review_status"] != "unreviewed" for s in siblings):
        db.table("templates").update({"review_status": "reviewed"}).eq(
            "id", clause["template_id"]
        ).execute()

    return updated


BULK_KEEP_REVIEWER_NOTES = "Bulk approval of fixed_boilerplate clauses"


def bulk_keep_boilerplate_clauses(template_id: str, db=None) -> list[dict]:
    """Lever 1 (2026-08-02 review-velocity request): Nitesh doesn't need
    to independently evaluate every fixed_boilerplate clause one at a
    time — they're identical structure across matters, unlike
    llm_fillable clauses whose generated content actually varies. One
    action keeps every currently-unreviewed fixed_boilerplate clause on
    a template, dropping (for example) NDA's review from 12 decisions to
    3 (just the llm_fillable ones).

    Scope, deliberately conservative per the user's own framing ("only
    ones that haven't been touched by clause-content changes since last
    seed... seems safer"): restricted to clause_type='fixed_boilerplate'
    AND review_status='unreviewed'. This achieves the safety property
    asked for without needing TICKET-4's not-yet-built content_hash
    column — a clause that's already been reviewed (kept/redrafted/
    deleted) is excluded from this action's scope entirely, so bulk-keep
    can never silently overwrite an existing human review decision, no
    matter what happened to its content since.

    Reuses review_clause() per clause (not a single denormalized bulk
    row) — see the docstring below for why a single clause_reviews row
    covering multiple clauses isn't possible under the current schema,
    and why one row per clause with matching reviewer_notes is the
    correct trade rather than a migration for this.
    """
    db = db if db is not None else service_client()

    clauses = (
        db.table("template_clauses")
        .select("id")
        .eq("template_id", template_id)
        .eq("clause_type", "fixed_boilerplate")
        .eq("review_status", "unreviewed")
        .execute()
        .data
        or []
    )

    return [
        review_clause(clause["id"], "keep", reviewer_notes=BULK_KEEP_REVIEWER_NOTES, db=db)
        for clause in clauses
    ]
