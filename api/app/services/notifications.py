"""In-app notifications (Litigation Intelligence + eCourts, 27 Aug 2026).
No email/SMS/WhatsApp -- per spec, in-app only for this phase; no such
channel infrastructure exists in this codebase to integrate with anyway
(confirmed during the forensic review: no SMTP/SendGrid/Resend/Twilio
anywhere in api/).

Deduplication (spec Sections 8/13: "no duplicate notifications"): every
notification carries a deterministic dedupe_key, enforced by a real
UNIQUE(user_id, dedupe_key) constraint (0025_litigation_intelligence_
ecourts.sql), not just an application-level check-then-insert race.
create_notification() upserts on that constraint -- calling it twice for
the same logical event is always a no-op the second time, from any
calling code path, not just this module's own callers.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger("vidhidesk.notifications")


def _dedupe_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def notify_hearing_listed(sc, *, organization_id: str, user_id: str, matter_id: str, matter_title: str, hearing_date: str, court: str | None, bench: str | None, item_no: str | None) -> dict[str, Any] | None:
    key = _dedupe_key("hearing_listed", matter_id, hearing_date)
    body_parts = [f"Your matter \"{matter_title}\" is listed on {hearing_date}."]
    if court:
        body_parts.append(f"Court Room: {court}.")
    if bench:
        body_parts.append(f"Bench: {bench}.")
    if item_no:
        body_parts.append(f"Item No: {item_no}.")
    return _create(
        sc,
        organization_id=organization_id,
        user_id=user_id,
        matter_id=matter_id,
        type_="hearing_listed",
        title="Hearing listed",
        body=" ".join(body_parts),
        dedupe_key=key,
    )


def notify_brief_ready(sc, *, organization_id: str, user_id: str, matter_id: str, matter_title: str, hearing_date: str, brief_id: str, version: int) -> dict[str, Any] | None:
    key = _dedupe_key("brief_ready", matter_id, hearing_date, brief_id, str(version))
    return _create(
        sc,
        organization_id=organization_id,
        user_id=user_id,
        matter_id=matter_id,
        type_="brief_ready",
        title="Hearing brief ready for review",
        body=f"Your hearing brief for \"{matter_title}\" ({hearing_date}) is ready for review.",
        dedupe_key=key,
    )


def _create(sc, *, organization_id: str, user_id: str, matter_id: str, type_: str, title: str, body: str, dedupe_key: str) -> dict[str, Any] | None:
    existing = (
        sc.table("notifications")
        .select("id")
        .eq("user_id", user_id)
        .eq("dedupe_key", dedupe_key)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return None  # already notified -- not an error, just a no-op
    try:
        inserted = sc.table("notifications").insert(
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "matter_id": matter_id,
                "type": type_,
                "title": title,
                "body": body,
                "dedupe_key": dedupe_key,
            }
        ).execute()
        return inserted.data[0] if inserted.data else None
    except Exception:
        # A unique_violation here means a genuine race (two sync runs
        # landed the same dedupe_key between the SELECT above and this
        # INSERT) -- benign, same as account_security's insert-once
        # pattern (app/routers/auth.py). Any other failure is logged.
        logger.warning("notifications._create failed for user_id=%s dedupe_key=%s", user_id, dedupe_key, exc_info=True)
        return None
