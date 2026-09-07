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

    # A CNR change invalidates every prior sync result for THIS row --
    # without this, the previous CNR's provider_metadata/sync_status/
    # last_synced_at keep displaying (now mislabeled under the new CNR)
    # until the next sync happens to succeed. Found by testing two real
    # CNRs on the same matter: the old case's petitioner/court/FIR data
    # was still visible under the new, never-yet-synced CNR. Reset
    # unconditionally on any cnr_number write (including clearing it to
    # None), not just when the value differs from the current one.
    if "cnr_number" in payload:
        payload = {
            **payload,
            "sync_status": "idle",
            "provider_metadata": None,
            "last_synced_at": None,
            "last_error": None,
            # Same staleness bug provider_metadata's reset above guards
            # against (see comment) -- these typed mirrors (0028) would
            # otherwise keep showing the PREVIOUS CNR's court/judge/status/
            # parties under the new, not-yet-synced CNR.
            "court_name": None,
            "judge": None,
            "case_status": None,
            "petitioners": [],
            "respondents": [],
        }

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
