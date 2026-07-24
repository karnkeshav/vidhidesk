#!/usr/bin/env python3
"""Indian Kanoon API spike (Sprint 0, deliverable 2).

Run from /api:

    source .venv/bin/activate
    python scripts/ik_spike.py

Requires INDIAN_KANOON_API_TOKEN to be set (loaded from the repo-root
.env automatically). Performs three real searches against the live API
and prints the raw JSON responses so auth, response shapes, and quota
behaviour can be confirmed by hand — this script makes no assumptions
about what "correct" looks like beyond "the request didn't error."

Test cases:
  1. A statute/topic query with no obvious case name — exercises plain
     keyword search: "Carriage by Road Act damages"
  2. A well-known Supreme Court case name — should return a strong match:
     "Kesavananda Bharati State of Kerala"
  3. A nonsense case name that should return no match — proves the
     citation verifier's "unverified" path has something real to key off:
     "Zzqxvthorpe Nonexistent Fictional Litigant"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services.indian_kanoon import IndianKanoonClient, IndianKanoonError  # noqa: E402

QUERIES = [
    ("Carriage by Road Act damages", None),
    ("Kesavananda Bharati State of Kerala", "supremecourt"),
    ("Zzqxvthorpe Nonexistent Fictional Litigant", None),
]


def main() -> int:
    settings = get_settings()
    if not settings.indian_kanoon_api_token:
        print(
            "INDIAN_KANOON_API_TOKEN is not set in the environment / repo-root .env.\n"
            "Nothing to spike — set it and re-run.",
            file=sys.stderr,
        )
        return 1

    client = IndianKanoonClient(settings=settings)

    for i, (query, court) in enumerate(QUERIES, start=1):
        print(f"\n{'=' * 80}\nQUERY {i}: {query!r} (court={court!r})\n{'=' * 80}")
        try:
            result = client.search(query, court=court, max_pages=1)
        except IndianKanoonError as exc:
            print(f"ERROR: {exc}")
            continue

        print(json.dumps(result, indent=2, ensure_ascii=False)[:4000])

        docs = result.get("docs", [])
        print(f"\n--- {len(docs)} result(s) on page 0 ---")
        if docs:
            top = docs[0]
            top_id = top.get("tid") or top.get("docid") or top.get("doc_id")
            print(f"Top result: {top.get('title')!r} (id={top_id})")
            if top_id is not None:
                print(f"\nFetching full doc for top result (id={top_id})...")
                try:
                    doc = client.get_doc(str(top_id))
                    print(json.dumps(doc, indent=2, ensure_ascii=False)[:2000])
                except IndianKanoonError as exc:
                    print(f"ERROR fetching doc: {exc}")

    print(
        "\n\nDone. Confirm: (1) auth worked (no 401/403), (2) response field "
        "names above match what indian_kanoon.py expects (docid/tid, title, "
        "court, date fields), (3) query 3 genuinely returned zero/low-confidence "
        "results, (4) check response headers or account dashboard for quota use."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
