"""Sprint 3.6 Phase 2A — TICKET-25 supplementary diagnostic (read-only).

The main diagnostic (diagnose_legal_grounds.py) landed almost entirely on
Groq (real-time Gemini rate-limit pressure, TICKET-21) and surfaced only
1 malformed sample — but that sample, plus both of Phase 2's original
failures, all landed on gemini-2.5-flash-lite specifically. This script
calls gemini-2.5-flash-lite DIRECTLY (bypassing the gateway's pool/
failover order) for the same legal_grounds prompt across all 6 matters,
to get a clean, model-isolated malformed-rate measurement uncontaminated
by which tier the failover chain happened to land on this run.

Run standalone: python scripts/diagnose_legal_grounds_flash_lite.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

from app.config import get_settings  # noqa: E402
from app.db import service_client  # noqa: E402
from app.services import clause_generator as cg  # noqa: E402
from app.services.llm_gateway import SYSTEM_PROMPTS, _call_gemini  # noqa: E402
from app.services.pii_mask import SupabaseMaskStore, mask_text, unmask_text  # noqa: E402

TARGETS = ["APP-01", "CIV-01", "COM-01", "IA-01", "PROP-03", "RERA-01"]
REPEATS = 2  # 6 x 2 = 12 direct flash-lite samples


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


def one_direct_attempt(matter_id: str, outline_id: str, db, settings) -> dict:
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

    masked_prompt = mask_text(prompt, mask_map, entities, auto_detect_names=True)
    formatted = f"<user_instruction>\n{masked_prompt}\n</user_instruction>"
    system_prompt = SYSTEM_PROMPTS["clause_drafter"]

    text, model = _call_gemini(settings, "gemini-2.5-flash-lite", system_prompt, [("user", formatted)])
    mask_store.save(mask_map)
    unmasked = unmask_text(text, mask_map)

    parsed = cg._extract_json(unmasked)
    return {"raw_text": unmasked, "raw_chars": len(unmasked), "parsed_ok": parsed is not None}


def main() -> None:
    db = service_client()
    settings = get_settings()
    results = []
    for label in TARGETS:
        matter_id, outline_id, title = resolve_matter_outline(db, label)
        print(f"\n=== {label} ({title}) — gemini-2.5-flash-lite direct ===")
        for i in range(1, REPEATS + 1):
            try:
                r = one_direct_attempt(matter_id, outline_id, db, settings)
            except Exception as exc:  # noqa: BLE001 — diagnostic script, report and continue
                print(f"  attempt {i}: PROVIDER_ERROR {exc}")
                results.append({"label": label, "attempt": i, "parsed_ok": None, "error": str(exc)})
                continue
            r["label"] = label
            r["attempt"] = i
            results.append(r)
            status = "PARSED_OK" if r["parsed_ok"] else "MALFORMED"
            print(f"  attempt {i}: {status} raw_chars={r['raw_chars']}")
            if not r["parsed_ok"]:
                print("    ---- RAW TEXT (full) ----")
                print("    " + r["raw_text"].replace("\n", "\n    "))
                print("    ---- END RAW TEXT ----")

    scored = [r for r in results if r.get("parsed_ok") is not None]
    n_malformed = sum(1 for r in scored if not r["parsed_ok"])
    print(f"\n=== gemini-2.5-flash-lite ISOLATED: {n_malformed}/{len(scored)} malformed ({(n_malformed / len(scored) if scored else 0):.0%}) ===")

    out_path = API_ROOT.parent / "docs" / "40_Validation" / "TICKET-25_diagnostic_flash_lite_isolated_2026-08-09.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Full raw evidence written to {out_path}")


if __name__ == "__main__":
    main()
