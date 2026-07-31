#!/usr/bin/env python3
"""Nightly dead-link recheck (TRD §3.3: "a nightly job re-checks cached
URLs (HTTP 200) to catch dead links").

For every citation with status='verified', HEAD the stored ik_url. A
non-200 marks the row `stale=true` — never deleted, per CLAUDE.md's
auditability posture (Hard Rule 4) and because a transient IK outage
shouldn't destroy a previously-confirmed verification. A row that
recovers (200 again) has `stale` cleared.

The renderer gate (see app/services/citation_render.py) treats
`status='verified' AND NOT stale` as the only condition allowed to
produce a live hyperlink — so marking a row stale here immediately
downgrades it to the grey "unverified" rendering without touching
`status` itself.

Run from /api:
    source .venv/bin/activate
    python scripts/recheck_citations.py

Wire this up to something that actually fires nightly — a GitHub Actions
scheduled workflow is the natural free-tier choice (see
.github/workflows/recheck_citations.yml). Nothing in this repo triggers
it on a timer by itself.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.db import service_client  # noqa: E402

PAGE_SIZE = 200


def recheck_all(db=None) -> dict[str, int]:
    db = db if db is not None else service_client()
    stats = {"checked": 0, "ok": 0, "marked_stale": 0, "recovered": 0, "errors": 0}

    offset = 0
    while True:
        rows = (
            db.table("citations")
            .select("id,ik_url,stale")
            .eq("status", "verified")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
        )
        if not rows:
            break

        for row in rows:
            stats["checked"] += 1
            now = datetime.now(timezone.utc).isoformat()
            try:
                resp = httpx.head(row["ik_url"], timeout=15.0, follow_redirects=True)
                ok = resp.status_code == 200
            except httpx.HTTPError:
                ok = False

            if ok:
                stats["ok"] += 1
                if row.get("stale"):
                    stats["recovered"] += 1
                db.table("citations").update(
                    {"stale": False, "last_checked_at": now}
                ).eq("id", row["id"]).execute()
            else:
                stats["marked_stale"] += 1
                db.table("citations").update(
                    {"stale": True, "last_checked_at": now}
                ).eq("id", row["id"]).execute()

        offset += PAGE_SIZE

    return stats


def main() -> int:
    stats = recheck_all()
    print(
        f"Rechecked {stats['checked']} verified citation(s): "
        f"{stats['ok']} ok, {stats['marked_stale']} marked stale, "
        f"{stats['recovered']} recovered."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
