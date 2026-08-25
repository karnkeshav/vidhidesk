#!/usr/bin/env python3
"""Seed curated RERA filing-walkthrough content into `rera_guides`.

THIS FILE CONTAINS NO REAL LEGAL CONTENT YET. The single group below
(Maharashtra / project-registration) is a PLACEHOLDER showing the exact
shape a real, source-cited procedure must take — every field is a TODO,
`source_url` is empty, and `verification_status` is left at the honest
default ("unverified"). Do not run this against production as-is.

Why this exists / how to use it (CLAUDE.md Hard Rule 3 + this module's own
design, app/services/rera.py's docstring: "Never fabricates legal/
procedural content... every walkthrough step is a row someone curated
into `rera_guides` with a source_url... never synthesizes a
plausible-looking step"):

  1. Find the real, official source for one (state, procedure) — the
     state RERA authority's own portal, a public circular/notification,
     or an official user manual for the e-filing portal.
  2. Replace the WALKTHROUGH_GROUPS entry below (or add a new one) with
     the real steps, each with:
       - heading / instruction: what the advocate is being told to do,
         drawn directly from the source (paraphrase for clarity, but
         never invent a document/requirement/portal step the source
         doesn't state).
       - required_documents: only documents the source actually lists.
       - portal_url: the real e-filing portal URL for that step, if any.
       - warnings: real cautions from the source (e.g. a hard deadline,
         a common rejection reason) — omit (None) if the source has none.
       - source_url: the exact page/document you took this from. Required
         to ever set verification_status to "verified" — see below.
       - verification_status: "unverified" until a human has actually
         checked the step against the live source at seed time, then
         "verified" (only pair with a real source_url) or
         "pending_verification" if checked but not fully confirmed.
  3. Run: `python scripts/seed_rera_guides.py` from /api (idempotent —
     upserts on the (state, procedure, step_no) unique index, safe to
     re-run after edits).

Uses service_client() because rera_guides is shared reference data, not
user-owned — same as templates/state_rules (see
app/services/rera.py's module docstring for the RLS reasoning: reads are
open to any authenticated user via rera_guides_read_authenticated,
migration 0002_rls.sql; writes are service-role only, which this script
uses).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

# --- One example group per (state, procedure). Add more groups for more
# procedures/states once you have real, source-cited content for them. ---
WALKTHROUGH_GROUPS: list[dict[str, Any]] = [
    {
        "state": "Maharashtra",
        "procedure": "project-registration",
        "steps": [
            {
                "step_no": 1,
                "heading": "TODO: replace with the real first step's title",
                "instruction": (
                    "TODO: replace with the real instruction text for this "
                    "step, paraphrased from the official source below — do "
                    "not invent details the source does not state."
                ),
                "required_documents": [],  # TODO: e.g. ["Title deed", "Layout plan approved by competent authority"]
                "portal_url": None,  # TODO: e.g. "https://maharera.mahaonline.gov.in/"
                "warnings": None,  # TODO: e.g. a real deadline or common rejection reason, or leave None
                "source_url": None,  # REQUIRED before verification_status can be "verified"
                "last_verified": None,  # TODO: "YYYY-MM-DD" the human actually checked this against the source
                "verification_status": "unverified",
            },
        ],
    },
]


def seed_rera_guides(groups: list[dict[str, Any]]) -> None:
    db = service_client()
    total = 0
    for group in groups:
        state = group["state"]
        procedure = group["procedure"]
        rows = [
            {
                "state": state,
                "procedure": procedure,
                "step_no": step["step_no"],
                "heading": step.get("heading"),
                "instruction": step["instruction"],
                "required_documents": step.get("required_documents", []),
                "portal_url": step.get("portal_url"),
                "warnings": step.get("warnings"),
                "source_url": step.get("source_url"),
                "last_verified": step.get("last_verified"),
                "verification_status": step.get("verification_status", "unverified"),
            }
            for step in group["steps"]
        ]
        if any(r["verification_status"] == "verified" and not r["source_url"] for r in rows):
            raise ValueError(
                f"{state}/{procedure}: verification_status='verified' requires a source_url — "
                "never mark a step verified without one."
            )
        db.table("rera_guides").upsert(rows, on_conflict="state,procedure,step_no").execute()
        print(f"Upserted {len(rows)} step(s) for {state} / {procedure}")
        total += len(rows)
    print(f"Done — {total} row(s) upserted across {len(groups)} group(s).")


if __name__ == "__main__":
    seed_rera_guides(WALKTHROUGH_GROUPS)
