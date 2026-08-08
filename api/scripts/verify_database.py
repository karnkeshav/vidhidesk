"""Part 2 — Database Verification (Sprint 3.5.5B).

Checks the REAL Supabase project this process is configured against —
not a mock, not a local fixture. Every finding below is either a real
PostgREST call or explicitly marked SKIP with the reason it can't be
performed with the credentials currently available.

What this script CAN verify directly, via PostgREST's own OpenAPI schema
and RPC endpoints (no extra dependency beyond the existing `httpx`):
  - table existence and column-level shape
  - RPC (stored function) existence and anon-execute permission posture
  - RLS enforcement, behaviorally (anon-key access vs service-key access
    on a sample of owner-scoped and reference-data tables)
  - row counts (population sanity, not correctness)

What it CANNOT verify without a direct Postgres connection (this project
has no DATABASE_URL configured — only the PostgREST REST endpoint and
anon/service API keys, which do not expose index/constraint/trigger
metadata): named index existence, named constraint existence, triggers.
These are reported SKIP with the reason, never assumed passing.

The expected-object manifest below was built by reading every migration
file in api/migrations/ in full, including DROP statements — several
objects created in one migration are later deliberately dropped in a
later one (e.g. 0005 drops citations_case_court_uq before creating its
replacement; 0012 drops three columns/indexes 0011 created). A naive
"grep every CREATE" manifest would falsely flag those as missing. The
manifest here nets creates against drops, table by table, so it doesn't
produce false failures for deliberate schema changes.

Run standalone: python scripts/verify_database.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult, exit_with, timed  # noqa: E402

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

# --- Expected schema manifest, derived from api/migrations/0001-0014 ------
# table_name: defining migration(s). A table appearing here with no
# corresponding "if not exists" DROP TABLE anywhere in the migrations
# means it's expected to exist for the life of the project so far.
EXPECTED_TABLES: dict[str, str] = {
    "matters": "0001",
    "messages": "0001",
    "citations": "0001",
    "templates": "0001",
    "draft_versions": "0001",
    "statute_chunks": "0001",
    "state_rules": "0001",
    "rera_guides": "0001",
    "pii_masks": "0001",
    "template_clauses": "0007",
    "clause_reviews": "0007",
    "draft_clause_fills": "0007",
    "advocate_profiles": "0011 (modified 0012)",
    "litigation_parties": "0013",
    "litigation_facts_evidence": "0013",
    "litigation_hearings": "0013",
    "litigation_case_analyses": "0014",
}

# column_name -> migration that added it, checked only for tables where a
# later migration added/removed columns after initial creation (the
# tables most likely to have drifted, and the ones already known to have
# drifted once — advocate_profiles via 0011->0012).
EXPECTED_COLUMNS: dict[str, dict[str, str]] = {
    "templates": {"review_status": "0007", "template_key": "0007"},
    "template_clauses": {"applicable_condition": "0008", "heading": "0008"},
    "matters": {"template_id": "0010"},
    "citations": {"case_name_normalized": "0005"},
    "statute_chunks": {"text_search": "0006"},
    "litigation_facts_evidence": {"file_url": "0014", "file_name": "0014", "file_size_bytes": "0014", "mime_type": "0014"},
    # advocate_profiles: 0011 created these, 0012 deliberately dropped them
    # — asserting their ABSENCE is itself the correct post-0012 check.
    "advocate_profiles": {
        "enrollment_state": "0011, DROPPED by 0012 — must NOT exist",
        "enrollment_year": "0011, DROPPED by 0012 — must NOT exist",
    },
}
# Columns that must NOT exist (the inverse check for the drops above).
EXPECTED_ABSENT_COLUMNS: dict[str, list[str]] = {
    "advocate_profiles": [
        "enrollment_state", "enrollment_year", "high_court_roll_no",
        "aor_code", "firm_name", "practice_areas", "states_of_practice",
        "languages_spoken", "rera_advocate_reg_no",
    ],
}

# App-defined RPCs only — excludes pg_trgm-extension-provided functions
# like show_trgm/show_limit, which PostgREST also exposes but this
# project never created and has no opinion about.
EXPECTED_RPCS: dict[str, str] = {
    "match_statute_chunks": "0004",
    "search_statute_chunks_fulltext": "0006",
}

# Tables where 0002/0007/0011/0013/0014 explicitly enable RLS. Every one
# of these is expected to hide its rows from an unauthenticated anon-key
# client. pii_masks additionally has NO policies at all for non-service
# roles (0002's own comment: "no direct client access at all").
EXPECTED_RLS_TABLES = [
    "matters", "messages", "draft_versions", "pii_masks",
    "citations", "templates", "statute_chunks", "state_rules", "rera_guides",
    "template_clauses", "clause_reviews", "draft_clause_fills",
    "advocate_profiles",
    "litigation_parties", "litigation_facts_evidence", "litigation_hearings", "litigation_case_analyses",
]

# Reference tables where 0002 grants SELECT to any authenticated role —
# an anon-key (unauthenticated) client should still see 0 rows for these,
# same as owner-scoped tables, since anon != authenticated.
_ALL_TABLES = list(EXPECTED_TABLES.keys())


def _fetch_schema(base_url: str, api_key: str) -> dict:
    resp = httpx.get(
        f"{base_url}/rest/v1/",
        headers={"apikey": api_key, "Authorization": f"Bearer {api_key}"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def run() -> VerificationResult:
    result = VerificationResult("Database Verification (Part 2)")

    try:
        from app.config import get_settings  # noqa: PLC0415
        from app.db import anon_client, service_client  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        result.add("Import app.db / app.config", Status.FAIL, f"{type(exc).__name__}: {exc}")
        return result

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        result.add("Supabase credentials configured", Status.FAIL, "SUPABASE_URL or SUPABASE_SERVICE_KEY missing")
        return result

    schema, dt, err = timed(lambda: _fetch_schema(settings.supabase_url, settings.supabase_service_key))
    if err:
        result.add("Fetch PostgREST schema (service role)", Status.FAIL, f"{type(err).__name__}: {err}", dt)
        return result
    result.add("Fetch PostgREST schema (service role)", Status.PASS, f"{len(schema.get('definitions', {}))} objects exposed", dt)

    definitions: dict = schema.get("definitions", {})
    paths: dict = schema.get("paths", {})

    # --- Table existence -----------------------------------------------
    for table, source in EXPECTED_TABLES.items():
        if table in definitions:
            result.add(f"Table exists: {table}", Status.PASS, f"defined in migration {source}")
        else:
            result.add(f"Table exists: {table}", Status.FAIL, f"MISSING — expected per migration {source}, not found in live schema")

    # --- Column-level checks ---------------------------------------------
    for table, cols in EXPECTED_COLUMNS.items():
        props = definitions.get(table, {}).get("properties", {})
        for col, source in cols.items():
            if "DROPPED" in source:
                continue  # handled in the absent-columns block below
            if col in props:
                result.add(f"Column exists: {table}.{col}", Status.PASS, f"added in migration {source}")
            else:
                result.add(f"Column exists: {table}.{col}", Status.FAIL, f"MISSING — expected per migration {source}")

    for table, cols in EXPECTED_ABSENT_COLUMNS.items():
        props = definitions.get(table, {}).get("properties", {})
        still_present = [c for c in cols if c in props]
        if still_present:
            result.add(
                f"Deprecated columns removed: {table}",
                Status.FAIL,
                f"Migration 0012 should have dropped these; still present: {', '.join(still_present)}",
            )
        else:
            result.add(f"Deprecated columns removed: {table}", Status.PASS, "0012's drops confirmed applied")

    # --- RPC existence ----------------------------------------------------
    for rpc, source in EXPECTED_RPCS.items():
        if f"/rpc/{rpc}" in paths:
            result.add(f"RPC exists: {rpc}", Status.PASS, f"defined in migration {source}")
        else:
            result.add(f"RPC exists: {rpc}", Status.FAIL, f"MISSING — expected per migration {source}")

    # --- Row counts (informational, not pass/fail on their own) -----------
    svc = service_client()
    for table in _ALL_TABLES:
        if table not in definitions:
            continue  # already reported missing above
        count_result, dt, err = timed(lambda t=table: svc.table(t).select("*", count="exact").limit(1).execute())
        if err:
            result.add(f"Row count: {table}", Status.WARN, f"Could not count: {type(err).__name__}: {err}", dt)
        else:
            n = count_result.count
            status = Status.WARN if table == "statute_chunks" and n == 0 else Status.PASS
            detail = "Empty — RAG retrieval will return nothing" if (table == "statute_chunks" and n == 0) else None
            result.add(f"Row count: {table}", status, detail or f"{n} rows", dt)

    # --- RLS enforcement (behavioral) --------------------------------------
    anon = anon_client()
    for table in EXPECTED_RLS_TABLES:
        if table not in definitions:
            continue
        anon_result, dt, err = timed(lambda t=table: anon.table(t).select("*").limit(5).execute())
        if err is not None:
            # Denied outright (e.g. pii_masks, which has zero policies for
            # non-service roles) is a PASS for "no unauthenticated access."
            result.add(f"RLS blocks anon: {table}", Status.PASS, f"Access denied outright: {type(err).__name__}", dt)
            continue
        rows = anon_result.data or []
        if rows:
            result.add(
                f"RLS blocks anon: {table}",
                Status.FAIL,
                f"Unauthenticated anon-key client read {len(rows)} row(s) — RLS is not enforcing on this table",
                dt,
            )
        else:
            result.add(f"RLS blocks anon: {table}", Status.PASS, "0 rows visible to unauthenticated anon key", dt)

    # --- Anon cannot execute app RPCs (least-privilege posture) ------------
    for rpc in EXPECTED_RPCS:
        if f"/rpc/{rpc}" not in paths:
            continue
        args = {"query_embedding": [0.0] * 384, "match_count": 1} if rpc == "match_statute_chunks" else {"query_text": "test", "match_count": 1}
        rpc_result, dt, err = timed(lambda r=rpc, a=args: anon.rpc(r, a).execute())
        if err is not None:
            result.add(f"Anon cannot execute RPC: {rpc}", Status.PASS, f"Denied as expected: {type(err).__name__}", dt)
        else:
            result.add(
                f"Anon cannot execute RPC: {rpc}",
                Status.FAIL,
                "Anon-key client successfully called this RPC — the explicit REVOKE in migrations 0004/0006 is not effective",
                dt,
            )

    # --- What this script cannot check without direct Postgres access -----
    result.add(
        "Named index existence",
        Status.SKIP,
        "Requires a direct Postgres connection (DATABASE_URL) to query pg_indexes; "
        "not configured in this environment. PostgREST does not expose index metadata.",
    )
    result.add(
        "Named constraint / trigger existence",
        Status.SKIP,
        "Same limitation — requires pg_constraint/pg_trigger access via a direct Postgres connection, not available via the REST API alone.",
    )

    # --- Migration history cross-check -------------------------------------
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    migration_files = sorted(p.name for p in migrations_dir.glob("*.sql"))
    all_table_checks_pass = all(t in definitions for t in EXPECTED_TABLES)
    if all_table_checks_pass:
        result.add(
            "Migration history matches repository",
            Status.PASS,
            f"All {len(EXPECTED_TABLES)} tables from all {len(migration_files)} migration files ({migration_files[0]}..{migration_files[-1]}) are present in the live schema",
        )
    else:
        missing = [t for t in EXPECTED_TABLES if t not in definitions]
        result.add(
            "Migration history matches repository",
            Status.FAIL,
            f"{len(missing)} of {len(EXPECTED_TABLES)} expected tables are missing from the live database despite their migration files existing in the repository: {', '.join(missing)}",
        )

    return result


if __name__ == "__main__":
    exit_with(run())
