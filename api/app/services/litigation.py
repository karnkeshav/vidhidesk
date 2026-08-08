from __future__ import annotations

from typing import Any
from supabase import Client


def list_parties(matter_id: str, db: Client) -> list[dict[str, Any]]:
    """List all parties for a given litigation matter ordered by party_type and party_number."""
    res = (
        db.table("litigation_parties")
        .select("*")
        .eq("matter_id", matter_id)
        .order("party_number")
        .execute()
    )
    return res.data or []


def add_party(matter_id: str, payload: dict[str, Any], db: Client) -> dict[str, Any]:
    """Add a new party (Petitioner/Respondent/Plaintiff/Defendant) to a matter."""
    data = {**payload, "matter_id": matter_id}
    res = db.table("litigation_parties").insert(data).execute()
    return res.data[0] if res.data else data


def delete_party(party_id: str, matter_id: str, db: Client) -> bool:
    """Delete a party belonging to a matter."""
    res = (
        db.table("litigation_parties")
        .delete()
        .eq("id", party_id)
        .eq("matter_id", matter_id)
        .execute()
    )
    return bool(res.data)


def list_evidence(matter_id: str, db: Client) -> list[dict[str, Any]]:
    """List all chronological fact & exhibit entries for a matter."""
    res = (
        db.table("litigation_facts_evidence")
        .select("*")
        .eq("matter_id", matter_id)
        .order("event_date", nullsfirst=False)
        .execute()
    )
    return res.data or []


def add_evidence(matter_id: str, payload: dict[str, Any], db: Client) -> dict[str, Any]:
    """Add a new fact or exhibit item to a matter."""
    data = {**payload, "matter_id": matter_id}
    res = db.table("litigation_facts_evidence").insert(data).execute()
    return res.data[0] if res.data else data


def delete_evidence(evidence_id: str, matter_id: str, db: Client) -> bool:
    """Delete a fact entry belonging to a matter."""
    res = (
        db.table("litigation_facts_evidence")
        .delete()
        .eq("id", evidence_id)
        .eq("matter_id", matter_id)
        .execute()
    )
    return bool(res.data)


def list_hearings(matter_id: str, db: Client) -> list[dict[str, Any]]:
    """List all scheduled and past court hearings for a matter."""
    res = (
        db.table("litigation_hearings")
        .select("*")
        .eq("matter_id", matter_id)
        .order("hearing_date")
        .execute()
    )
    return res.data or []


def add_hearing(matter_id: str, payload: dict[str, Any], db: Client) -> dict[str, Any]:
    """Log a new court hearing for a matter."""
    data = {**payload, "matter_id": matter_id}
    res = db.table("litigation_hearings").insert(data).execute()
    return res.data[0] if res.data else data
