"""RERA & Real Estate — Phase 1 backend (state/procedure walkthrough data +
walkthrough progress).

Property deeds and RERA complaints are deliberately NOT handled here — they
reuse the existing generic templates/template_clauses/draft_versions engine
(app/services/contracts.py::generate_draft, already module-agnostic) exactly
like any Contracts template. See
docs/30_Implementation/RERA_BACKEND_INTEGRATION_CONTRACT.md for the full
reuse rationale. This module only covers the two capabilities that had no
existing equivalent anywhere in the codebase: curated state/procedure/step
content, and per-advocate walkthrough progress.

Never fabricates legal/procedural content (CLAUDE.md, this sprint's brief):
every walkthrough step this module returns is a row someone curated into
`rera_guides` with a source_url — if a (state, procedure) pair has zero
rows, the API says so honestly (empty list / 404), it never synthesizes a
plausible-looking step.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.schemas import RERA_PHASE1_STATES


class RERAError(ValueError):
    """Mirrors the project's established plain-ValueError-on-bad-input
    convention (CaseAnalysisError, PleadingOutlineError, ClauseGeneratorError,
    DocumentComposerError) so the router can translate it to HTTP 400 the
    same way every other module does."""


def _validate_state(state: str) -> None:
    if state not in RERA_PHASE1_STATES:
        raise RERAError(
            f"'{state}' is not yet supported for RERA filing walkthroughs "
            f"(Phase 1 covers {', '.join(RERA_PHASE1_STATES)} only — ADR-010). "
            "No walkthrough content exists for this state; do not guess at one."
        )


# --- Read-only reference data (rera_guides) — shared, not user-owned,
# reachable via the caller's own RLS-scoped client since
# rera_guides_read_authenticated (migration 0002_rls.sql) already grants
# read access to any authenticated user, same as templates/state_rules. ----


def list_procedures(state: str, db) -> list[dict[str, Any]]:
    """Distinct procedures actually curated for a state, derived from real
    rera_guides rows — never a hardcoded procedure enum, so adding a new
    procedure is purely a data change (this sprint's "no schema
    duplication per state" requirement)."""
    _validate_state(state)
    rows = (
        db.table("rera_guides")
        .select("procedure")
        .eq("state", state)
        .execute()
        .data
        or []
    )
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["procedure"]] = counts.get(r["procedure"], 0) + 1
    return [
        {"state": state, "procedure": proc, "step_count": n}
        for proc, n in sorted(counts.items())
    ]


def list_walkthrough_steps(state: str, procedure: str, db) -> list[dict[str, Any]]:
    _validate_state(state)
    rows = (
        db.table("rera_guides")
        .select("*")
        .eq("state", state)
        .eq("procedure", procedure)
        .order("step_no")
        .execute()
        .data
        or []
    )
    return rows


def _step_ids_for(state: str, procedure: str, db) -> list[str]:
    rows = (
        db.table("rera_guides")
        .select("id")
        .eq("state", state)
        .eq("procedure", procedure)
        .order("step_no")
        .execute()
        .data
        or []
    )
    return [r["id"] for r in rows]


# --- Matter ownership/module check (mirrors _get_matter_or_404 in
# litigation.py/contracts.py — duplicated rather than imported across
# routers per this project's established convention, see
# clause_generator.py's _extract_json docstring for the same reasoning). ----


def _validate_rera_matter(matter_id: str, db) -> dict[str, Any]:
    resp = db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        # RLS makes another user's matter look identical to a missing one —
        # same no-ownership-probing-oracle posture as every other module.
        raise RERAError(f"Matter {matter_id} not found")
    matter = resp.data[0]
    if matter.get("module") != "rera":
        raise RERAError(
            f"Matter {matter_id} is not a RERA matter (module={matter.get('module')!r}) — "
            "walkthrough progress can only be attached to a RERA matter."
        )
    return matter


# --- Walkthrough progress (rera_walkthrough_progress, migration 0019) ------
# Owner-scoped directly by user_id (not matter-derived — see migration
# 0019's docstring for why), so every read/write here goes through the
# caller's own RLS-scoped user.db client, exactly like matters.py itself.


def get_progress(user_id: str, state: str, procedure: str, matter_id: str | None, db) -> dict[str, Any] | None:
    _validate_state(state)
    query = (
        db.table("rera_walkthrough_progress")
        .select("*")
        .eq("state", state)
        .eq("procedure", procedure)
    )
    query = query.is_("matter_id", "null") if matter_id is None else query.eq("matter_id", matter_id)
    rows = query.limit(1).execute().data
    return rows[0] if rows else None


def upsert_progress(
    user_id: str,
    state: str,
    procedure: str,
    matter_id: str | None,
    current_step_no: int | None,
    mark_step_complete_id: str | None,
    mark_step_incomplete_id: str | None,
    db,
) -> dict[str, Any]:
    """Create-or-update the caller's progress for (state, procedure[, matter]).
    Every step id referenced (mark complete/incomplete) and every
    current_step_no is validated against the REAL curated step list for
    this (state, procedure) — a request can't mark a step "complete" that
    doesn't exist, and can't set current_step_no past the last real step."""
    _validate_state(state)
    if matter_id is not None:
        _validate_rera_matter(matter_id, db)

    step_ids = _step_ids_for(state, procedure, db)
    if not step_ids:
        raise RERAError(
            f"No walkthrough content exists yet for state={state!r} procedure={procedure!r} — "
            "cannot track progress against a procedure with zero curated steps."
        )
    step_id_set = set(step_ids)
    total_steps = len(step_ids)

    if current_step_no is not None and not (1 <= current_step_no <= total_steps):
        raise RERAError(f"current_step_no must be between 1 and {total_steps} for this procedure")
    if mark_step_complete_id is not None and mark_step_complete_id not in step_id_set:
        raise RERAError(f"Step {mark_step_complete_id} does not belong to state={state!r} procedure={procedure!r}")
    if mark_step_incomplete_id is not None and mark_step_incomplete_id not in step_id_set:
        raise RERAError(f"Step {mark_step_incomplete_id} does not belong to state={state!r} procedure={procedure!r}")

    existing = get_progress(user_id, state, procedure, matter_id, db)
    completed: set[str] = set(existing["completed_step_ids"]) if existing else set()
    if mark_step_complete_id is not None:
        completed.add(mark_step_complete_id)
    if mark_step_incomplete_id is not None:
        completed.discard(mark_step_incomplete_id)
    # Only ever keep ids that are still real steps for this procedure —
    # guards against stale ids surviving a future content edit.
    completed &= step_id_set

    resolved_step_no = current_step_no if current_step_no is not None else (
        existing["current_step_no"] if existing else 1
    )
    is_complete = len(completed) == total_steps

    row = {
        "user_id": user_id,
        "matter_id": matter_id,
        "state": state,
        "procedure": procedure,
        "current_step_no": resolved_step_no,
        "completed_step_ids": sorted(completed),
        "is_complete": is_complete,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing:
        updated = db.table("rera_walkthrough_progress").update(row).eq("id", existing["id"]).execute()
        return updated.data[0] if updated.data else {**existing, **row}

    # started_at is set explicitly here, on first insert only, rather than
    # relying on the column's `default now()` (migration 0019) — a
    # Postgrest INSERT does return DB-defaulted columns in practice, but
    # this keeps the row this function returns self-consistent with
    # RERAWalkthroughProgressOut's required field regardless of what the
    # underlying client happens to echo back.
    insert_row = {**row, "started_at": row["updated_at"]}
    inserted = db.table("rera_walkthrough_progress").insert(insert_row).execute()
    return inserted.data[0] if inserted.data else insert_row
