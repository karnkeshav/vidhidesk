"""Sprint 3.6 Phase 2A — one-off: capture raw text for a post-json_mode
malformed legal_grounds response (the regression run's CIV-01 failure had
no raw text persisted). Read-only, does not use generate_clause()."""

from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

from app.db import service_client  # noqa: E402
from app.services import clause_generator as cg  # noqa: E402
from app.services.llm_gateway import generate_json  # noqa: E402
from app.services.pii_mask import SupabaseMaskStore  # noqa: E402

db = service_client()
matters = db.table("matters").select("id,title").eq("module", "litigation").execute().data
matter_id = next(m["id"] for m in matters if m["id"] == "e92dfd99-c935-464f-ab97-9e2120f92065")
outlines = db.table("litigation_pleading_outlines").select("id").eq("matter_id", matter_id).order("version_no", desc=True).limit(1).execute().data
outline_id = outlines[0]["id"]

for i in range(3):
    ctx = cg._clause_context(matter_id, outline_id, db)
    prompt = cg._prompt_legal_grounds(ctx)
    matter = ctx["matter"]
    parties = ctx["parties"]
    mask_store = SupabaseMaskStore(service_client())
    mask_map = mask_store.load(matter_id)
    entities = [("PARTY", p["party_name"]) for p in parties]
    result, parsed = generate_json(prompt, task_type="clause_drafter", mask_map=mask_map, entities=entities, auto_detect_names=True, max_repair_attempts=0)
    mask_store.save(mask_map)
    print(f"\nattempt {i+1}: model={result.provider}/{result.model} parsed_ok={parsed is not None}")
    if parsed is None:
        print("RAW TEXT:")
        print(result.text)
