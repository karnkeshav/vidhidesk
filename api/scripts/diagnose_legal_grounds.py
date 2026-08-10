"""Sprint 3.6 Phase 2A — TICKET-25 root-cause diagnostic (read-only).

Reproduces clause_generator.py's exact legal_grounds generation path
(context assembly -> prompt build -> PII mask -> llm_gateway.generate())
WITHOUT going through generate_clause() / inserting a
litigation_pleading_clauses row — this sprint's diagnostic phase must not
pollute production clause-version history with throwaway pre-redesign
attempts against outlines the redesign is about to make obsolete (unlike
the actual regression run in Phase 2A §5, which DOES persist for real).

For every attempt this prints: matter, model actually used, whether the
raw text parsed as JSON, and — critically, since Phase 2's own report
never persisted this — the FULL RAW TEXT of every malformed attempt, so
root causes can be classified from real evidence, not re-guessed from a
2/6 aggregate.

Run standalone: python scripts/diagnose_legal_grounds.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

from app.db import service_client  # noqa: E402
from app.services import clause_generator as cg  # noqa: E402
from app.services.llm_gateway import generate  # noqa: E402
from app.services.pii_mask import SupabaseMaskStore  # noqa: E402

REPEATS_PER_MATTER = 4  # 6 matters x 4 = 24 fresh samples, plus the 6 already on record from Phase 2 = 30 total

TARGETS = ["APP-01", "CIV-01", "COM-01", "IA-01", "PROP-03", "RERA-01"]


def resolve_matter_outline(db, label: str) -> tuple[str, str, str]:
    matters = db.table("matters").select("id,title").eq("module", "litigation").execute().data
    cands = [m for m in matters if label in m["title"]]
    best = None
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
            best = (c["id"], outlines[0]["id"], c["title"])
            break
    if best is None:
        raise RuntimeError(f"No matter+outline found for {label}")
    return best


def one_attempt(matter_id: str, outline_id: str, db) -> dict:
    ctx = cg._clause_context(matter_id, outline_id, db)
    prompt = cg._prompt_legal_grounds(ctx)
    matter = ctx["matter"]
    parties = ctx["parties"]

    mask_store = SupabaseMaskStore(service_client())
    mask_map = mask_store.load(matter_id)
    entities = [("PARTY", p["party_name"]) for p in parties]
    if p_addr := [p["address"] for p in parties if p.get("address")]:
        entities += [("ADDR", a) for a in p_addr]
    if matter.get("client_name"):
        entities.append(("PARTY", matter["client_name"]))

    result = generate(
        prompt,
        task_type="clause_drafter",
        mask_map=mask_map,
        entities=entities,
        auto_detect_names=True,
    )
    mask_store.save(mask_map)

    parsed = cg._extract_json(result.text)
    return {
        "prompt_chars": len(prompt),
        "prompt": prompt,
        "provider": result.provider,
        "model": result.model,
        "requested_model": result.requested_model,
        "degraded": result.degraded,
        "fallback_chain": result.fallback_chain,
        "latency_ms": result.latency_ms,
        "raw_text": result.text,
        "raw_text_chars": len(result.text),
        "parsed_ok": parsed is not None,
        "parsed": parsed,
        "n_statutes_in_context": len(ctx["applicable_statutes"]),
        "n_case_law_in_context": len(ctx["verified_case_law"]),
        "n_issues_in_context": len(ctx["outline"].get("legal_issues") or []),
        "n_causes_in_context": len(ctx["outline"].get("cause_of_action") or []),
    }


def main() -> None:
    db = service_client()
    all_results = []
    for label in TARGETS:
        matter_id, outline_id, title = resolve_matter_outline(db, label)
        print(f"\n=== {label} ({title}) matter={matter_id} outline={outline_id} ===")
        for i in range(1, REPEATS_PER_MATTER + 1):
            r = one_attempt(matter_id, outline_id, db)
            r["label"] = label
            r["attempt"] = i
            all_results.append(r)
            status = "PARSED_OK" if r["parsed_ok"] else "MALFORMED"
            print(
                f"  attempt {i}: {status} model={r['provider']}/{r['model']} "
                f"(requested={r['requested_model']}, degraded={r['degraded']}) "
                f"prompt_chars={r['prompt_chars']} raw_chars={r['raw_text_chars']} "
                f"latency_ms={r['latency_ms']}"
            )
            if not r["parsed_ok"]:
                print(f"    fallback_chain={r['fallback_chain']}")
                print("    ---- RAW TEXT (full) ----")
                print("    " + r["raw_text"].replace("\n", "\n    "))
                print("    ---- END RAW TEXT ----")

    n_malformed = sum(1 for r in all_results if not r["parsed_ok"])
    print(f"\n=== SUMMARY: {n_malformed}/{len(all_results)} malformed ({n_malformed / len(all_results):.0%}) ===")
    by_model: dict[str, list[bool]] = {}
    for r in all_results:
        by_model.setdefault(f"{r['provider']}/{r['model']}", []).append(r["parsed_ok"])
    for model, oks in sorted(by_model.items()):
        fails = sum(1 for ok in oks if not ok)
        print(f"  {model}: {fails}/{len(oks)} malformed")

    out_path = Path(__file__).resolve().parent.parent.parent / "docs" / "40_Validation" / "TICKET-25_diagnostic_raw_output_2026-08-09.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nFull raw evidence written to {out_path}")


if __name__ == "__main__":
    main()
