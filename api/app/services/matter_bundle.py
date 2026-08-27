"""Matter Intelligence Bundle assembly (Litigation Intelligence + eCourts,
27 Aug 2026). Pure DB reads -- no LLM call, no network call -- gathering
everything hearing_brief.py needs to ground a brief in this matter's own
record. Scoped by matter_id only; the caller's `db` (an RLS-scoped
user_client, per every router in this codebase) is what actually enforces
organization isolation -- this module never uses service_client(), so a
bundle can never cross an organization boundary regardless of what
matter_id is passed in.

Every category is either populated from a real stored record or explicitly
listed in `missing` -- never silently omitted, never fabricated. This
mirrors case_analysis.py's deterministic/LLM split discipline applied one
layer earlier: the bundle itself is 100% deterministic, assembled before
any model ever sees it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MatterBundleError(ValueError):
    """Mirrors case_analysis.py's CaseAnalysisError / limitation.py's
    plain-ValueError convention -- the router translates this to HTTP 400."""


@dataclass
class MatterBundle:
    matter: dict[str, Any]
    parties: list[dict[str, Any]]
    chronology: list[dict[str, Any]]
    pleadings: list[dict[str, Any]]
    hearings: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    research: list[dict[str, Any]]
    verified_citations: list[dict[str, Any]]
    lawyer_notes: list[str]
    missing: list[str] = field(default_factory=list)

    def as_prompt_text(self) -> str:
        """Renders the bundle as the text handed to the LLM -- every
        section is explicitly labeled so the model's required source_refs
        (see llm_gateway.py's hearing_analyst prompt) name something a
        human reviewer can actually find."""
        lines: list[str] = [f"MATTER: {self.matter.get('title', 'Untitled matter')}"]
        if self.matter.get('court_category'):
            lines.append(f"Forum on record: {self.matter['court_category']} ({self.matter.get('jurisdiction_state', 'India')})")
        if self.matter.get('cnr_number'):
            lines.append(f"CNR: {self.matter['cnr_number']}")

        lines.append("\nPARTIES:")
        for p in self.parties:
            lines.append(f"- {p['party_type']} #{p['party_number']}: {p['party_name']}")

        lines.append("\nCHRONOLOGY:")
        for f in self.chronology:
            date = f.get("event_date") or "undated"
            lines.append(f"- [{date}] {f['fact_summary']}")

        lines.append("\nPLEADINGS:")
        if self.pleadings:
            for p in self.pleadings:
                lines.append(f"- Pleading v{p.get('version_no')}, composed {p.get('created_at')}")
                for section in (p.get("composed_sections") or [])[:20]:
                    heading = section.get("heading", "")
                    text = str(section.get("text", ""))[:500]
                    lines.append(f"  [Pleading: {heading}] {text}")
        else:
            lines.append("- (none composed yet)")

        lines.append("\nPRIOR HEARINGS (most recent first):")
        if self.hearings:
            for h in self.hearings:
                lines.append(f"- Hearing {h.get('hearing_at')}, stage={h.get('stage')}, outcome={h.get('outcome')}")
                if h.get("arguments_made"):
                    lines.append(f"  [Hearing note, {h.get('hearing_at')}] Arguments made: {h['arguments_made']}")
                if h.get("judge_questions"):
                    lines.append(f"  [Hearing note, {h.get('hearing_at')}] Judge questions: {h['judge_questions']}")
                if h.get("opposing_counsel_position"):
                    lines.append(f"  [Hearing note, {h.get('hearing_at')}] Opposing counsel: {h['opposing_counsel_position']}")
                if h.get("next_steps"):
                    lines.append(f"  [Hearing note, {h.get('hearing_at')}] Next steps: {h['next_steps']}")
                if h.get("notes"):
                    lines.append(f"  [Hearing note, {h.get('hearing_at')}] Lawyer notes: {h['notes']}")
        else:
            lines.append("- (no prior hearings on record)")

        lines.append("\nORDERS (most recent first):")
        if self.orders:
            for o in self.orders:
                lines.append(f"- [Order dated {o.get('order_date')}] {(o.get('raw_text') or '')[:500]}")
                for d in (o.get("ai_extracted_directions") or []):
                    lines.append(f"  Direction: {d.get('direction')} (deadline: {d.get('deadline')}, complied: {d.get('complied')})")
        else:
            lines.append("- (no orders on record)")

        lines.append("\nEVIDENCE:")
        for e in self.evidence:
            lines.append(f"- {e.get('exhibit_number') or 'unmarked'}: {e.get('fact_summary')}")

        lines.append("\nVERIFIED RESEARCH / CITATIONS:")
        if self.verified_citations:
            for c in self.verified_citations:
                lines.append(f"- {c.get('case_name')} — {c.get('note', '')} (status: {c.get('status')})")
        else:
            lines.append("- (none)")

        if self.lawyer_notes:
            lines.append("\nLAWYER NOTES:")
            for n in self.lawyer_notes:
                lines.append(f"- {n}")

        if self.missing:
            lines.append("\nEXPLICITLY MISSING FROM THIS BUNDLE (do not assume these exist):")
            for m in self.missing:
                lines.append(f"- {m}")

        return "\n".join(lines)


def _sort_key(item: dict[str, Any], date_field: str) -> tuple[int, str]:
    date = item.get(date_field)
    return (1, "") if not date else (0, str(date))


def assemble_matter_bundle(matter_id: str, db, *, exclude_hearing_id: str | None = None) -> MatterBundle:
    """Assembles the Matter Intelligence Bundle for `matter_id` using the
    caller's own RLS-scoped `db` -- organization isolation is enforced by
    Postgres RLS on every table read here (0024_tenant_foundation.sql /
    0025_litigation_intelligence_ecourts.sql), not by any check in this
    function. `exclude_hearing_id`, when given, omits that hearing from
    the "prior hearings" section -- used when assembling a bundle to
    prepare FOR that hearing, so it doesn't see its own not-yet-happened
    listing as a "prior" hearing."""
    matter_rows = db.table("matters").select("*").eq("id", matter_id).execute().data
    if not matter_rows:
        raise MatterBundleError(f"Matter {matter_id} not found")
    matter = matter_rows[0]

    missing: list[str] = []

    parties = db.table("litigation_parties").select("*").eq("matter_id", matter_id).execute().data or []
    if not parties:
        missing.append("No parties recorded for this matter.")

    facts = db.table("litigation_facts_evidence").select("*").eq("matter_id", matter_id).execute().data or []
    chronology = sorted(facts, key=lambda f: _sort_key(f, "event_date"))
    if not facts:
        missing.append("No facts/chronology recorded for this matter.")

    pleading_drafts = (
        db.table("litigation_pleading_drafts")
        .select("*")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not pleading_drafts:
        missing.append("No composed pleading exists yet for this matter.")

    hearings_query = db.table("hearings").select("*").eq("matter_id", matter_id).order("hearing_at", desc=True)
    all_hearings = hearings_query.execute().data or []
    prior_hearings = [h for h in all_hearings if h["id"] != exclude_hearing_id]
    if not prior_hearings:
        missing.append("No prior hearing history recorded for this matter.")
    elif not any(h.get("arguments_made") or h.get("judge_questions") for h in prior_hearings):
        missing.append("No prior hearing carries argument notes or judge questions yet.")

    orders = (
        db.table("orders").select("*").eq("matter_id", matter_id).order("order_date", desc=True).execute().data or []
    )
    if not orders:
        missing.append("No orders on record for this matter.")

    documents = db.table("draft_versions").select("*").eq("matter_id", matter_id).execute().data or []

    research = (
        db.table("litigation_case_analyses")
        .select("*")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    verified_citations: list[dict[str, Any]] = []
    for r in research:
        for c in (r.get("possible_precedents") or []):
            if c.get("status") == "verified":
                verified_citations.append(c)
    if not verified_citations:
        missing.append("No verified case-law citations linked to this matter yet.")

    lawyer_notes = [h["notes"] for h in prior_hearings if h.get("notes")]

    return MatterBundle(
        matter=matter,
        parties=parties,
        chronology=[
            {
                "event_date": f.get("event_date"),
                "fact_summary": f["fact_summary"],
                "exhibit_number": f.get("exhibit_number"),
            }
            for f in chronology
        ],
        pleadings=pleading_drafts,
        hearings=prior_hearings,
        orders=orders,
        evidence=facts,
        documents=documents,
        research=research,
        verified_citations=verified_citations,
        lawyer_notes=lawyer_notes,
        missing=missing,
    )
