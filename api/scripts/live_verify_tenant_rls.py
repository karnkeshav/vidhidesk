"""Live verification for 0024_tenant_foundation.sql's RLS rewrite.

Same convention as live_verify_rls.py (real Supabase project, real signed-in
users, real inserts) -- not runnable offline / not part of pytest, because
RLS isolation cannot be faithfully reproduced in the in-process FakeDB the
rest of this test suite uses. Requires two pre-existing test accounts
(live_test_user_a / live_test_user_b, same as live_verify_rls.py) against
whichever Supabase project SUPABASE_URL/SUPABASE_ANON_KEY/SUPABASE_SERVICE_KEY
point at -- do NOT point this at production unless you intend to create and
then clean up real rows there.

Expanded 27 Aug 2026 (security/migration review follow-up) beyond the
original matters-only check: now exercises every ROOT table plus a
representative set of CHILD tables, covering SELECT/INSERT/UPDATE/DELETE
denial where the table's own RLS policy set actually defines those
operations (several child tables are intentionally SELECT+INSERT-only --
immutable-version tables with no UPDATE/DELETE policy for ANYONE, owner
included -- documented per-table below rather than assumed).

Run manually after applying 0024_tenant_foundation.sql, before relying on
it: `python scripts/live_verify_tenant_rls.py`

Coverage note, stated plainly rather than hidden: identical SQL policy
shape across tables is a strong argument by analogy, not proof that every
table behaves identically at runtime -- this script exercises each target
table directly for exactly that reason, rather than asserting the matters/
hearings result generalizes. Tables intentionally NOT covered here (fixture
complexity, not risk):
  - draft_clause_fills is covered IF a template_clauses row already exists
    in the target project (global reference data) -- SKIPPED with a clear
    message otherwise, since it has a NOT NULL FK to template_clauses this
    script does not attempt to fabricate.
  - litigation_pleading_clauses / litigation_pleading_drafts: same RLS
    shape as litigation_pleading_outlines (which IS covered, chained off
    the same litigation_case_analyses row) but one/two FK levels deeper
    (pleading_outline_id). Not independently exercised.
"""

import os
import sys

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("../.env")
url: str = os.environ["SUPABASE_URL"]
key: str = os.environ["SUPABASE_ANON_KEY"]
service_key: str = os.environ["SUPABASE_SERVICE_KEY"]

supabase_admin: Client = create_client(url, service_key)
supabase_anon: Client = create_client(url, key)

email_a = "live_test_user_a@vidhidesk.com"
email_b = "live_test_user_b@vidhidesk.com"
password = "SecurePassword123!"

auth_a = supabase_anon.auth.sign_in_with_password({"email": email_a, "password": password})
user_a_id = auth_a.user.id
user_a_client = create_client(url, key, options={"headers": {"Authorization": f"Bearer {auth_a.session.access_token}"}})

auth_b = supabase_anon.auth.sign_in_with_password({"email": email_b, "password": password})
user_b_id = auth_b.user.id
user_b_client = create_client(url, key, options={"headers": {"Authorization": f"Bearer {auth_b.session.access_token}"}})

failures: list[str] = []
cleanup_stack: list[tuple[str, str]] = []  # (table, row_id), deleted admin-side, LIFO


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        failures.append(label)


def skip(label: str, reason: str) -> None:
    print(f"[SKIP] {label} -- {reason}")


def run_isolation_checks(
    table: str,
    seed_row: dict,
    forge_row: dict,
    supports_update: bool,
    supports_delete: bool,
    label_prefix: str,
) -> str | None:
    """Seeds one row (as admin, owned by Org A's matter) and runs the
    A/B/C/D/E checks described in the module docstring. Returns the
    seeded row's id (for chaining a dependent table's fixture) or None if
    seeding itself failed. Registers the row for end-of-script cleanup."""
    try:
        seeded = supabase_admin.table(table).insert(seed_row).execute().data[0]
    except Exception as exc:
        check(f"{label_prefix}: seed row (admin)", False)
        print(f"       seed error: {exc}")
        return None
    row_id = seeded["id"]
    cleanup_stack.append((table, row_id))

    # A: User A (own org) can read it
    res_a = user_a_client.table(table).select("*").eq("id", row_id).execute()
    check(f"{label_prefix}: User A can SELECT own-org row", len(res_a.data) == 1)

    # B: User B (different org) cannot read it
    res_b = user_b_client.table(table).select("*").eq("id", row_id).execute()
    check(f"{label_prefix}: User B cannot SELECT other-org row", len(res_b.data) == 0)

    # C: User B cannot INSERT a row referencing Org A's parent (forgery)
    try:
        user_b_client.table(table).insert(forge_row).execute()
        check(f"{label_prefix}: User B insert referencing Org A rejected", False)
    except Exception:
        check(f"{label_prefix}: User B insert referencing Org A rejected", True)

    # D: User B cannot UPDATE it (RLS silently matches 0 rows, not an error)
    if supports_update:
        upd = user_b_client.table(table).update({"id": row_id}).eq("id", row_id).execute()
        check(f"{label_prefix}: User B cannot UPDATE other-org row", len(upd.data) == 0)
    else:
        skip(f"{label_prefix}: UPDATE denial", "table has no UPDATE policy at all (immutable-by-design, not an isolation gap)")

    # E: User B cannot DELETE it
    if supports_delete:
        # Re-verify the row still exists (admin) before/after to distinguish
        # "RLS correctly matched 0 rows" from "the row was never there".
        still_there_before = supabase_admin.table(table).select("id").eq("id", row_id).execute().data
        user_b_client.table(table).delete().eq("id", row_id).execute()
        still_there_after = supabase_admin.table(table).select("id").eq("id", row_id).execute().data
        check(
            f"{label_prefix}: User B cannot DELETE other-org row",
            len(still_there_before) == 1 and len(still_there_after) == 1,
        )
    else:
        skip(f"{label_prefix}: DELETE denial", "table has no DELETE policy at all (immutable-by-design, not an isolation gap)")

    return row_id


print("[Setup] Creating two separate organizations...")
org_a = supabase_admin.table("organizations").insert({"name": "RLS Test Org A", "organization_type": "individual"}).execute().data[0]
org_b = supabase_admin.table("organizations").insert({"name": "RLS Test Org B", "organization_type": "individual"}).execute().data[0]
cleanup_stack.append(("organizations", org_a["id"]))
cleanup_stack.append(("organizations", org_b["id"]))

supabase_admin.table("memberships").insert(
    {"organization_id": org_a["id"], "user_id": user_a_id, "role": "org_admin", "is_default": True}
).execute()
supabase_admin.table("memberships").insert(
    {"organization_id": org_b["id"], "user_id": user_b_id, "role": "org_admin", "is_default": True}
).execute()

# =====================================================================
# ROOT TABLES
# =====================================================================

print("\n[Root] matters")
matter_a = supabase_admin.table("matters").insert(
    {"user_id": user_a_id, "organization_id": org_a["id"], "title": "RLS Test Matter A", "module": "contracts"}
).execute().data[0]
cleanup_stack.append(("matters", matter_a["id"]))

res = user_a_client.table("matters").select("*").eq("id", matter_a["id"]).execute()
check("matters: User A can SELECT own-org matter", len(res.data) == 1)
res = user_b_client.table("matters").select("*").eq("id", matter_a["id"]).execute()
check("matters: User B cannot SELECT other-org matter", len(res.data) == 0)
try:
    user_b_client.table("matters").insert(
        {"user_id": user_b_id, "organization_id": org_a["id"], "title": "Should be rejected", "module": "contracts"}
    ).execute()
    check("matters: User B insert forging Org A rejected", False)
except Exception:
    check("matters: User B insert forging Org A rejected", True)
try:
    own_insert = user_a_client.table("matters").insert(
        {"user_id": user_a_id, "organization_id": org_a["id"], "title": "User A own insert", "module": "contracts"}
    ).execute()
    check("matters: User A insert into own org succeeds", len(own_insert.data) == 1)
    if own_insert.data:
        cleanup_stack.append(("matters", own_insert.data[0]["id"]))
except Exception as exc:
    check(f"matters: User A insert into own org succeeds ({exc})", False)
upd = user_b_client.table("matters").update({"title": "hijacked"}).eq("id", matter_a["id"]).execute()
check("matters: User B cannot UPDATE other-org matter", len(upd.data) == 0)
still_before = supabase_admin.table("matters").select("id").eq("id", matter_a["id"]).execute().data
user_b_client.table("matters").delete().eq("id", matter_a["id"]).execute()
still_after = supabase_admin.table("matters").select("id").eq("id", matter_a["id"]).execute().data
check("matters: User B cannot DELETE other-org matter", len(still_before) == 1 and len(still_after) == 1)

print("\n[Root] hearings")
run_isolation_checks(
    "hearings",
    seed_row={"user_id": user_a_id, "organization_id": org_a["id"], "title": "RLS Test Hearing A", "hearing_at": "2027-01-01T10:00:00Z"},
    forge_row={"user_id": user_b_id, "organization_id": org_a["id"], "title": "Forged hearing", "hearing_at": "2027-01-01T10:00:00Z"},
    supports_update=True,
    supports_delete=True,
    label_prefix="hearings",
)

# =====================================================================
# CHILD TABLE REPRESENTATIVES (all scoped via matter_a.organization_id)
# =====================================================================

print("\n[Child] messages")
run_isolation_checks(
    "messages",
    seed_row={"matter_id": matter_a["id"], "role": "user", "content": "RLS test message"},
    forge_row={"matter_id": matter_a["id"], "role": "user", "content": "Forged message"},
    supports_update=True,
    supports_delete=True,
    label_prefix="messages",
)

print("\n[Child] draft_versions")
run_isolation_checks(
    "draft_versions",
    seed_row={"matter_id": matter_a["id"], "version_no": 1},
    forge_row={"matter_id": matter_a["id"], "version_no": 2},
    supports_update=True,
    supports_delete=True,
    label_prefix="draft_versions",
)

print("\n[Child] litigation_parties")
run_isolation_checks(
    "litigation_parties",
    seed_row={"matter_id": matter_a["id"], "party_type": "Petitioner", "party_name": "RLS Test Party"},
    forge_row={"matter_id": matter_a["id"], "party_type": "Petitioner", "party_name": "Forged party"},
    supports_update=True,
    supports_delete=True,
    label_prefix="litigation_parties",
)

print("\n[Child] litigation_facts_evidence")
run_isolation_checks(
    "litigation_facts_evidence",
    seed_row={"matter_id": matter_a["id"], "fact_summary": "RLS test fact"},
    forge_row={"matter_id": matter_a["id"], "fact_summary": "Forged fact"},
    supports_update=True,
    supports_delete=True,
    label_prefix="litigation_facts_evidence",
)

print("\n[Child] litigation_hearings (matter-scoped docket, distinct from root `hearings`)")
run_isolation_checks(
    "litigation_hearings",
    seed_row={"matter_id": matter_a["id"], "hearing_date": "2027-01-01"},
    forge_row={"matter_id": matter_a["id"], "hearing_date": "2027-01-02"},
    supports_update=True,
    supports_delete=True,
    label_prefix="litigation_hearings",
)

print("\n[Child] consulting_analyses (SELECT+INSERT only -- immutable versions)")
run_isolation_checks(
    "consulting_analyses",
    seed_row={"matter_id": matter_a["id"], "version_no": 1, "question": "RLS test question"},
    forge_row={"matter_id": matter_a["id"], "version_no": 2, "question": "Forged question"},
    supports_update=False,
    supports_delete=False,
    label_prefix="consulting_analyses",
)

print("\n[Child, pleading-related 1/2] litigation_case_analyses (SELECT+INSERT only)")
case_analysis_id = run_isolation_checks(
    "litigation_case_analyses",
    seed_row={"matter_id": matter_a["id"], "version_no": 1},
    forge_row={"matter_id": matter_a["id"], "version_no": 2},
    supports_update=False,
    supports_delete=False,
    label_prefix="litigation_case_analyses",
)

if case_analysis_id:
    print("\n[Child, pleading-related 2/2] litigation_pleading_outlines (SELECT+INSERT only)")
    run_isolation_checks(
        "litigation_pleading_outlines",
        seed_row={"matter_id": matter_a["id"], "case_analysis_id": case_analysis_id, "version_no": 1},
        forge_row={"matter_id": matter_a["id"], "case_analysis_id": case_analysis_id, "version_no": 2},
        supports_update=False,
        supports_delete=False,
        label_prefix="litigation_pleading_outlines",
    )
else:
    skip("litigation_pleading_outlines", "litigation_case_analyses seed failed, no case_analysis_id to chain off")

print("\n[Child, fixture-dependent] draft_clause_fills")
existing_clause = supabase_admin.table("template_clauses").select("id").limit(1).execute().data
if not existing_clause:
    skip("draft_clause_fills", "no template_clauses row exists in this project -- cannot construct a valid NOT NULL FK without fabricating template content")
else:
    template_clause_id = existing_clause[0]["id"]
    draft_version_id = run_isolation_checks(
        "draft_versions",
        seed_row={"matter_id": matter_a["id"], "version_no": 99},
        forge_row={"matter_id": matter_a["id"], "version_no": 98},
        supports_update=False,
        supports_delete=False,
        label_prefix="draft_versions (fixture for draft_clause_fills, not re-counted)",
    )
    if draft_version_id:
        run_isolation_checks(
            "draft_clause_fills",
            seed_row={
                "draft_version_id": draft_version_id,
                "template_clause_id": template_clause_id,
                "generated_text": "RLS test text",
                "prompt": "RLS test prompt",
                "model_used": "test",
            },
            forge_row={
                "draft_version_id": draft_version_id,
                "template_clause_id": template_clause_id,
                "generated_text": "Forged text",
                "prompt": "Forged prompt",
                "model_used": "test",
            },
            supports_update=True,
            supports_delete=True,
            label_prefix="draft_clause_fills",
        )

# =====================================================================
# Cleanup (admin, reverse order -- children before their parents)
# =====================================================================
print("\n[Cleanup] Removing test rows...")
for table, row_id in reversed(cleanup_stack):
    try:
        supabase_admin.table(table).delete().eq("id", row_id).execute()
    except Exception as exc:
        print(f"       cleanup warning: could not delete {table}/{row_id}: {exc}")

if failures:
    print(f"\n{len(failures)} check(s) FAILED: {failures}")
    sys.exit(1)
print("\nAll checks passed.")
