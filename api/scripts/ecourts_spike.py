#!/usr/bin/env python3
"""eCourts (eCourtsIndia) API spike.

Referenced by app/services/court_data_gateway.py's module docstring
("RE-VERIFY every shape here against a live response with a real key --
see scripts/ecourts_spike.py") but never actually written until now --
found missing while investigating why court_advocates/case_advocate_links/
interlocutory_applications had no population code (2026-09-07).

Purpose: dump the RAW, untouched JSON for case_lookup() and
causelist_batch() against a real CNR so the advocate/interlocutory-
application/judge-name field shapes can be confirmed before any code
tries to parse them. CourtDataGateway.case_lookup() only extracts
cnr/courtName/judges/caseStatus/petitioners/respondents today -- those
were confirmed against a real response on 2026-09-06 (see that method's
own docstring); advocate names and IA data are believed to be present
somewhere in the same courtCaseData blob but their field names are NOT
yet confirmed. Guessing them was the cause of a prior bug (case_lookup
read the wrong response envelope) -- this script exists so the next
attempt is grounded in a real response instead of another guess.

Run from /api:

    source .venv/bin/activate
    python scripts/ecourts_spike.py <CNR>

Requires ECOURTS_API_KEY to be set (loaded from the repo-root .env
automatically). Writes the raw JSON for both calls to
scripts/_ecourts_spike_output/<CNR>_case_lookup.json and
..._causelist_batch.json so they can be inspected by hand or pasted back
for the extraction code to be written against real field names. Makes no
assumptions about what "correct" looks like beyond "the request didn't
error" -- same posture as ik_spike.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services.court_data_gateway import (  # noqa: E402
    CourtDataGateway,
    CourtDataGatewayError,
    CourtDataNotConfiguredError,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "_ecourts_spike_output"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/ecourts_spike.py <CNR>", file=sys.stderr)
        return 1
    cnr = sys.argv[1].strip()

    settings = get_settings()
    if not settings.ecourts_api_key:
        print(
            "ECOURTS_API_KEY is not set in the environment / repo-root .env.\n"
            "Nothing to spike -- set it and re-run.",
            file=sys.stderr,
        )
        return 1

    gateway = CourtDataGateway(settings=settings)
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\n{'=' * 80}\ncase_lookup({cnr!r})\n{'=' * 80}")
    try:
        detail = gateway.case_lookup(cnr)
    except (CourtDataGatewayError, CourtDataNotConfiguredError) as exc:
        print(f"ERROR: {exc}")
    else:
        out_path = OUTPUT_DIR / f"{cnr}_case_lookup.json"
        out_path.write_text(json.dumps(detail.raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Typed fields already extracted: cnr={detail.cnr!r} court={detail.court_name!r} "
              f"judge={detail.judge!r} status={detail.status!r}")
        print(f"petitioners={detail.petitioners} respondents={detail.respondents}")
        print(f"Full raw response written to {out_path}")
        print("Inspect it for advocate names and interlocutory-application fields --")
        print("look inside data.courtCaseData for keys near petitioners/respondents/judges.")

    print(f"\n{'=' * 80}\ncauselist_batch([{cnr!r}])\n{'=' * 80}")
    try:
        results = gateway.causelist_batch([cnr])
    except (CourtDataGatewayError, CourtDataNotConfiguredError) as exc:
        print(f"ERROR: {exc}")
    else:
        entry = results.get(cnr)
        out_path = OUTPUT_DIR / f"{cnr}_causelist_batch.json"
        out_path.write_text(
            json.dumps(entry.raw if entry else {}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if entry:
            print(f"has_causelist={entry.has_causelist} court={entry.court!r} bench={entry.bench!r} "
                  f"date={entry.date!r}")
        else:
            print(f"No causelist entry returned for {cnr!r} (not listed, or CNR not recognized).")
        print(f"Full raw response written to {out_path}")
        print("Inspect it for a bench/judge NAMES list (court_hearings_causelist.judge_names is text[]) --")
        print("the typed CauselistEntry above only carries a single 'bench' string today.")

    print(
        "\n\nDone. Confirm: (1) auth worked (no 401/403), (2) advocate field name(s) "
        "inside courtCaseData, (3) interlocutory-application field name(s) if present "
        "(may not exist in this endpoint at all -- IAs might only ever come from "
        "manual entry), (4) the causelist judge-names field, if any. Do not write "
        "extraction code against anything not seen directly in the JSON files this "
        "script wrote."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
