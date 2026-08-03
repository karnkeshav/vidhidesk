"""Shared seed utilities for VidhiDesk contract template seed scripts.
Extracted to eliminate duplicate logic across templates (Sprint 3 / Templates Expansion).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.db import service_client


class ReviewedClauseConflict(Exception):
    """A re-seed would silently change the baseline text under a clause
    that has already been reviewed.
    """


def prune_orphaned_clauses(db: Any, template_id: str, current_clause_keys: set[str]) -> None:
    """Delete template_clauses rows whose clause_key no longer appears in
    the script's CLAUSES list, preserving referenced rows safely.
    """
    existing = (
        db.table("template_clauses")
        .select("id,clause_key")
        .eq("template_id", template_id)
        .execute()
        .data
        or []
    )
    for row in existing:
        if row["clause_key"] in current_clause_keys:
            continue
        clause_id = row["id"]
        has_fills = bool(
            db.table("draft_clause_fills").select("id").eq("template_clause_id", clause_id).limit(1).execute().data
        )
        has_reviews = bool(
            db.table("clause_reviews").select("id").eq("clause_id", clause_id).limit(1).execute().data
        )
        if has_fills or has_reviews:
            print(
                f"WARNING: orphaned template_clauses row {clause_id} "
                f"(clause_key={row['clause_key']!r}) is referenced — not deleted."
            )
            continue
        db.table("template_clauses").delete().eq("id", clause_id).execute()
        print(f"Pruned orphaned template_clauses row {clause_id} (clause_key={row['clause_key']!r})")


def write_clauses_preserving_review(db: Any, template_id: str, clauses: list[dict]) -> None:
    """Upsert template_clauses without silently overwriting reviewed clause content."""
    existing_by_key = {
        row["clause_key"]: row
        for row in (
            db.table("template_clauses")
            .select("id,clause_key,source_text,review_status")
            .eq("template_id", template_id)
            .execute()
            .data
            or []
        )
    }

    protected_keys: set[str] = set()
    conflicts: list[tuple[str, str]] = []
    for clause in clauses:
        existing = existing_by_key.get(clause["clause_key"])
        if not existing or existing["review_status"] not in ("kept", "redrafted"):
            continue
        protected_keys.add(clause["clause_key"])
        if existing["source_text"] != clause["source_text"]:
            conflicts.append((clause["clause_key"], existing["review_status"]))

    if conflicts:
        lines = "\n".join(f"  - {key} (review_status={status!r})" for key, status in conflicts)
        raise ReviewedClauseConflict(
            "Re-seed HALTED — baseline text changed for reviewed clauses:\n" + lines
        )

    normal_rows = []
    for c in clauses:
        if c["clause_key"] in protected_keys:
            continue
        row = {
            "template_id": template_id,
            "clause_key": c["clause_key"],
            "display_order": c["display_order"],
            "clause_type": c["clause_type"],
            "applicable_condition": c.get("applicable_condition"),
            "heading": c.get("heading"),
            "source_text": c["source_text"],
            "current_text": c["source_text"],
        }
        if c["clause_key"] not in existing_by_key:
            row["review_status"] = "unreviewed"
        normal_rows.append(row)
    if normal_rows:
        db.table("template_clauses").upsert(normal_rows, on_conflict="template_id,clause_key").execute()

    for c in clauses:
        if c["clause_key"] not in protected_keys:
            continue
        db.table("template_clauses").update(
            {
                "display_order": c["display_order"],
                "clause_type": c["clause_type"],
                "applicable_condition": c.get("applicable_condition"),
                "heading": c.get("heading"),
            }
        ).eq("id", existing_by_key[c["clause_key"]]["id"]).execute()

    print(f"Upserted {len(normal_rows)} clause rows; preserved {len(protected_keys)} reviewed clause(s)")


def seed_template_pipeline(
    template_name: str,
    template_category: str,
    template_key: str,
    schema_path: Path,
    docx_path: str,
    states_supported: list[str],
    clauses: list[dict],
    state_rules: list[dict],
) -> str:
    """Executes full idempotent seed pipeline for a template."""
    db = service_client()
    schema_json = json.loads(schema_path.read_text())

    existing = (
        db.table("templates")
        .select("id")
        .eq("name", template_name)
        .eq("category", template_category)
        .execute()
        .data
    )
    if existing:
        template_id = existing[0]["id"]
        db.table("templates").update(
            {
                "schema_json": schema_json,
                "docx_path": docx_path,
                "states_supported": states_supported,
                "template_key": template_key,
            }
        ).eq("id", template_id).execute()
        print(f"Updated existing template row {template_id} for {template_name}")
    else:
        result = (
            db.table("templates")
            .insert(
                {
                    "name": template_name,
                    "category": template_category,
                    "schema_json": schema_json,
                    "docx_path": docx_path,
                    "states_supported": states_supported,
                    "template_key": template_key,
                }
            )
            .execute()
        )
        template_id = result.data[0]["id"]
        print(f"Inserted new template row {template_id} for {template_name}")

    write_clauses_preserving_review(db, template_id, clauses)
    prune_orphaned_clauses(db, template_id, {c["clause_key"] for c in clauses})

    for rule in state_rules:
        existing_rule = (
            db.table("state_rules")
            .select("id")
            .eq("state", rule["state"])
            .eq("instrument", rule["instrument"])
            .execute()
            .data
        )
        if existing_rule:
            db.table("state_rules").update(rule).eq("id", existing_rule[0]["id"]).execute()
        else:
            db.table("state_rules").insert(rule).execute()
    print(f"Upserted {len(state_rules)} state_rules rows for {template_name}")
    return template_id
