"""Part 2 (migration-file half) — Migration Verification (Sprint 3.5.5B).

This is deliberately distinct from verify_database.py, which checks the
LIVE schema state against what the migrations should have produced.
verify_migrations.py instead audits the migration FILES themselves —
static, repository-only checks that don't need any credentials at all:

  - sequential numbering, with no gaps and no duplicate number prefixes
    (docs/20_Engineering/Database_Architecture.md and docs/README.md
    previously claimed a duplicate 0009_ prefix — 0009_normalize_template_keys.sql
    vs. a planned 0009_litigation_pleadings_and_citations.sql referenced
    in LITIGATION_ARCHITECTURE.md. Running this check for real found that
    second file was never actually created — the litigation schema
    migration that shipped is 0013_litigation_schema.sql instead, correctly
    numbered. That prior claim was itself stale; see
    docs/40_Validation/Technical_Debt_Report_2026-08-06.md for the correction.)
  - each file's own stated idempotency claim (every migration's header
    comment says "Idempotent: safe to re-run") actually holds up under a
    lightweight structural check: every CREATE TABLE/INDEX/POLICY uses
    IF NOT EXISTS / OR REPLACE / DROP...IF EXISTS-then-CREATE, not a bare
    CREATE that would error on a second run

Run standalone: python scripts/verify_migrations.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult, exit_with  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_NUMBER_RE = re.compile(r"^(\d{4})_")
_BARE_CREATE_TABLE_RE = re.compile(r"create\s+table\s+(?!if\s+not\s+exists)", re.IGNORECASE)
_BARE_CREATE_INDEX_RE = re.compile(r"create\s+(?:unique\s+)?index\s+(?!if\s+not\s+exists)", re.IGNORECASE)
_BARE_ALTER_ADD_COLUMN_RE = re.compile(r"add\s+column\s+(?!if\s+not\s+exists)", re.IGNORECASE)
_CREATE_POLICY_RE = re.compile(r"create\s+policy\s+(\S+)", re.IGNORECASE)
_DROP_POLICY_RE = re.compile(r"drop\s+policy\s+if\s+exists\s+(\S+)", re.IGNORECASE)
# The project's real header convention (confirmed across 0001-0009) is a
# line matching "-- Idempotent: ...". A bare substring search for the
# word "idempotent" anywhere in the file is NOT the same check — 0011
# contains the phrase "Conservative Idempotent Backfill" describing only
# one INSERT statement, which a substring search would misread as a
# whole-file idempotency claim it never actually makes.
_IDEMPOTENT_HEADER_RE = re.compile(r"^--\s*idempotent\s*:", re.IGNORECASE | re.MULTILINE)


def run() -> VerificationResult:
    result = VerificationResult("Migration File Verification (Part 2, static)")

    if not MIGRATIONS_DIR.exists():
        result.add("Migrations directory exists", Status.FAIL, str(MIGRATIONS_DIR))
        return result

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    result.add("Migrations directory exists", Status.PASS, f"{len(files)} .sql files found")

    # --- Sequential numbering, gaps, duplicates ---------------------------
    numbers: dict[str, list[str]] = {}
    for f in files:
        m = _NUMBER_RE.match(f.name)
        if not m:
            result.add(f"Numbering: {f.name}", Status.WARN, "Filename doesn't start with a 4-digit number prefix")
            continue
        numbers.setdefault(m.group(1), []).append(f.name)

    duplicate_numbers = {n: fs for n, fs in numbers.items() if len(fs) > 1}
    if duplicate_numbers:
        for n, fs in duplicate_numbers.items():
            result.add(
                f"Duplicate migration number: {n}",
                Status.WARN,
                f"{len(fs)} files share this prefix: {', '.join(fs)} — makes apply-order ambiguous for a fresh environment.",
            )
    else:
        result.add("Duplicate migration numbers", Status.PASS, "Every migration has a unique number prefix")

    sorted_numbers = sorted(int(n) for n in numbers)
    gaps = [n for n in range(sorted_numbers[0], sorted_numbers[-1] + 1) if n not in sorted_numbers] if sorted_numbers else []
    if gaps:
        result.add("Sequence gaps", Status.WARN, f"Missing number(s) in the sequence: {gaps} (may be intentional if a migration was abandoned before merge; not necessarily a defect)")
    else:
        result.add("Sequence gaps", Status.PASS, f"Continuous from {sorted_numbers[0]:04d} to {sorted_numbers[-1]:04d}, no gaps")

    # --- Per-file idempotency structural check -----------------------------
    for f in files:
        sql = f.read_text()
        claims_idempotent = bool(_IDEMPOTENT_HEADER_RE.search(sql))
        issues: list[str] = []

        if _BARE_CREATE_TABLE_RE.search(sql):
            issues.append("CREATE TABLE without IF NOT EXISTS")
        if _BARE_CREATE_INDEX_RE.search(sql):
            issues.append("CREATE INDEX without IF NOT EXISTS")
        if _BARE_ALTER_ADD_COLUMN_RE.search(sql):
            issues.append("ADD COLUMN without IF NOT EXISTS")

        created_policies = set(_CREATE_POLICY_RE.findall(sql))
        dropped_policies = set(_DROP_POLICY_RE.findall(sql))
        undropped_policies = created_policies - dropped_policies
        if undropped_policies:
            issues.append(f"CREATE POLICY without a matching DROP POLICY IF EXISTS first (re-run would fail): {', '.join(sorted(undropped_policies))}")

        label = f"Idempotency: {f.name}"
        if not claims_idempotent and not issues:
            result.add(label, Status.WARN, "Doesn't explicitly claim idempotency in its header comment, but no non-idempotent pattern detected either — likely fine, worth a header note")
        elif issues:
            result.add(label, Status.FAIL if claims_idempotent else Status.WARN, "; ".join(issues) + (" (header claims idempotent — this is a real inconsistency)" if claims_idempotent else ""))
        else:
            result.add(label, Status.PASS, "No bare CREATE/ADD COLUMN patterns found; consistent with its idempotency claim")

    return result


if __name__ == "__main__":
    exit_with(run())
