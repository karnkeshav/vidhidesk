from __future__ import annotations

from typing import Any

from supabase import Client


def get_or_create_tracking(matter_id: str, organization_id: str, db: Client) -> dict[str, Any]:
    rows = db.table("court_case_tracking").select("*").eq("matter_id", matter_id).limit(1).execute().data
    if rows:
        return rows[0]
    inserted = db.table("court_case_tracking").insert(
        {"matter_id": matter_id, "organization_id": organization_id}
    ).execute()
    return inserted.data[0]


def update_tracking(matter_id: str, organization_id: str, payload: dict[str, Any], db: Client) -> dict[str, Any]:
    existing = get_or_create_tracking(matter_id, organization_id, db)
    updated = db.table("court_case_tracking").update(payload).eq("id", existing["id"]).execute()

    # matters.cnr_number predates this table (migration 0013) and is
    # still what the existing Litigation matter overview displays --
    # mirrored here so "CNR belongs to the Matter" stays true for the
    # reader, not just architecturally. court_case_tracking.cnr_number
    # remains the one eCourts sync actually reads; this is a display
    # convenience, not a second source of truth for sync logic.
    if "cnr_number" in payload:
        db.table("matters").update({"cnr_number": payload["cnr_number"]}).eq("id", matter_id).execute()

    return updated.data[0] if updated.data else existing
