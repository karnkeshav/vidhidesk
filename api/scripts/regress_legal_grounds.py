"""Sprint 3.6 Phase 2A — TICKET-25 regression (WORK ITEM 5).

Re-runs the SAME methodology Phase 2's own evaluation used
(docs/40_Validation/Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md
§5): generate_all_clauses() for real against the same 6 real certification
matters (APP-01, CIV-01, COM-01, IA-01, PROP-03, RERA-01), starting from
each matter's existing, already-reviewed Pleading Outline — never a fresh
outline. This IS a persisting run (new litigation_pleading_clauses rows),
matching Phase 2's own precedent (E36) of leaving real evidence on the
record, not a throwaway diagnostic.

Measures, for legal_grounds specifically: malformed rate, citation
(statute) rate, precedent (case law) usage. Also composes each matter's
pleading to confirm the new legal_grounds path doesn't break end-to-end
composition.

Run standalone: python scripts/regress_legal_grounds.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

from app.db import service_client  # noqa: E402
from app.services import clause_generator as cg  # noqa: E402
from app.services import document_composer as dc  # noqa: E402

TARGETS = ["APP-01", "CIV-01", "COM-01", "IA-01", "PROP-03", "RERA-01"]


def resolve_matter_outline(db, label: str) -> tuple[str, str, str]:
    matters = db.table("matters").select("id,title").eq("module", "litigation").execute().data
    cands = [m for m in matters if label in m["title"]]
    for c in cands:
        outlines = (
            db.table("litigation_pleading_outlines")
            .select("id,version_no")
            .eq("matter_id", c["id"])
            .order("version_no", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if outlines:
            return c["id"], outlines[0]["id"], c["title"]
    raise RuntimeError(f"No matter+outline found for {label}")


def main() -> None:
    db = service_client()
    start = time.monotonic()
    all_legal_grounds = []
    compose_results = []

    for label in TARGETS:
        matter_id, outline_id, title = resolve_matter_outline(db, label)
        print(f"\n=== {label} ({title}) ===")
        clauses = cg.generate_all_clauses(matter_id, outline_id, db)
        legal_grounds_row = next(c for c in clauses if c["clause_type"] == "legal_grounds")
        all_legal_grounds.append({"label": label, **legal_grounds_row})

        malformed = bool(legal_grounds_row.get("generation_warning"))
        n_grounds = len((legal_grounds_row.get("content") or {}).get("grounds") or [])
        n_statute_refs = len(legal_grounds_row.get("statute_refs") or [])
        n_grounded_statutes = sum(1 for r in (legal_grounds_row.get("statute_refs") or []) if r.get("grounded"))
        n_case_law_refs = len(legal_grounds_row.get("case_law_refs") or [])
        n_verified_case_law = sum(1 for r in (legal_grounds_row.get("case_law_refs") or []) if r.get("status") == "verified")

        print(f"  legal_grounds: {'MALFORMED' if malformed else 'OK'} model={legal_grounds_row.get('model_used')}")
        print(f"    grounds={n_grounds} statute_refs={n_statute_refs} (grounded={n_grounded_statutes}) "
              f"case_law_refs={n_case_law_refs} (verified={n_verified_case_law}) confidence={legal_grounds_row.get('confidence')}")
        if not malformed:
            print("    ---- assembled text ----")
            print("    " + (legal_grounds_row["content"]["text"] or "").replace("\n", "\n    "))
            print("    ---- end ----")

        # Auto-approve every non-warning clause (Phase 2's own convention —
        # a scripted stand-in for advocate review, evaluation purposes only)
        # then compose, to confirm end-to-end integration still works.
        for clause in clauses:
            if not clause.get("generation_warning"):
                cg.review_clause(clause["id"], matter_id, "approved", db)
        draft = dc.compose_pleading(matter_id, outline_id, db)
        compose_results.append({"label": label, "missing_clauses": draft["missing_clauses"], "n_sections": len(draft["composed_sections"])})
        print(f"  composed: {len(draft['composed_sections'])}/14 sections, missing={draft['missing_clauses']}")

    n_malformed = sum(1 for r in all_legal_grounds if r.get("generation_warning"))
    n_total = len(all_legal_grounds)
    n_with_statute = sum(1 for r in all_legal_grounds if r.get("statute_refs"))
    n_with_case_law = sum(1 for r in all_legal_grounds if any(c.get("status") == "verified" for c in (r.get("case_law_refs") or [])))

    print(f"\n=== REGRESSION SUMMARY ({time.monotonic() - start:.0f}s) ===")
    print(f"legal_grounds malformed rate: {n_malformed}/{n_total} ({n_malformed / n_total:.0%})")
    print(f"legal_grounds runs citing >=1 statute: {n_with_statute}/{n_total}")
    print(f"legal_grounds runs citing >=1 VERIFIED precedent: {n_with_case_law}/{n_total}")
    for r in compose_results:
        ok = "legal_grounds" not in r["missing_clauses"]
        print(f"  {r['label']}: {r['n_sections']}/14 composed, legal_grounds present={ok}")

    out_path = API_ROOT.parent / "docs" / "40_Validation" / "TICKET-25_regression_raw_output_2026-08-09.json"
    with open(out_path, "w") as f:
        json.dump({"legal_grounds": all_legal_grounds, "compose": compose_results}, f, indent=2, default=str)
    print(f"\nFull raw evidence written to {out_path}")


if __name__ == "__main__":
    main()
