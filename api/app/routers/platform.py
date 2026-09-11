"""Platform-owner API (Enhancement_Roadmap.md §4, migration
0024_tenant_foundation.sql). Every route here is gated by
app/auth.py::require_platform_owner -- a plain 403 for anyone else,
enforced server-side against the already-verified JWT email claim, never
a frontend-only check (principle #17).

Uses service_client() throughout (bypasses RLS) -- appropriate specifically
because require_platform_owner has already authorized cross-organization
visibility; no other router in this codebase should reach for
service_client() to read matter-scoped data the way this one does.

Metric approximations, stated plainly rather than hidden: this schema has
no dedicated activity/onboarding-event table yet (Enhancement_Roadmap.md
Section 2.4 anticipates one). "users_with_a_matter"/"users_with_a_draft"
and the onboarding funnel below are derived from existing timestamps on
matters/draft_versions/account_security -- real counts, not fabricated,
but approximations of "activity" rather than a purpose-built event log.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase_auth.errors import AuthApiError

from app.auth import CurrentUser, TRIAL_WINDOW, require_platform_owner
from app.db import service_client
from app.models.schemas import (
    MatterDemoUpdate,
    MatterOut,
    MembershipOut,
    OrganizationAccessUpdate,
    OrganizationDetailOut,
    OrganizationListItemOut,
    OrganizationOut,
    PlatformOverviewOut,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])
logger = logging.getLogger("vidhidesk.platform")

# Dashboard clarity (security review round 3, 27 Aug 2026): the owner
# must be able to see, per member, that ORGANIZATION access and this
# individual's own account_security state are two separate things --
# "Mark Organization Payment Made" does not repair an expired member
# trial. Mirrors the exact same precedence/logic as
# app/auth.py::_check_account_not_locked (payment_received bypasses
# everything; no row yet means "hasn't signed in via session-start yet";
# otherwise compare against TRIAL_WINDOW) so this can never silently
# drift from what actually gates the member's requests. Deliberately
# exposes only a coarse category, never the raw login_started_at
# timestamp or any other account_security field, to that member's
# organization co-owner -- "do not expose unnecessary sensitive account
# information".
def _account_status(row: dict | None) -> str:
    if row is None:
        return "not_started"
    if row.get("payment_received"):
        return "payment_received"
    login_started_at = row.get("login_started_at")
    if not login_started_at:
        return "not_started"
    started = datetime.fromisoformat(login_started_at.replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - started > TRIAL_WINDOW:
        return "trial_expired"
    return "trial_active"

_VALID_STATUSES = {"trial", "active", "suspended", "expired"}
_VALID_TYPES = {"individual", "firm"}


@router.get("/overview", response_model=PlatformOverviewOut)
def platform_overview(_owner: CurrentUser = Depends(require_platform_owner)):
    sc = service_client()
    orgs = sc.table("organizations").select("organization_type,subscription_status").execute().data
    matters = sc.table("matters").select("user_id").execute().data
    draft_matter_ids = {
        r["matter_id"] for r in sc.table("draft_versions").select("matter_id").execute().data
    }
    trial_rows = sc.table("account_security").select("user_id").execute().data

    users_with_a_matter = {m["user_id"] for m in matters if m.get("user_id")}

    users_with_a_draft: set[str] = set()
    if draft_matter_ids:
        matters_for_drafts = (
            sc.table("matters")
            .select("id,user_id")
            .in_("id", list(draft_matter_ids))
            .execute()
            .data
        )
        users_with_a_draft = {m["user_id"] for m in matters_for_drafts if m.get("user_id")}

    return PlatformOverviewOut(
        total_organizations=len(orgs),
        individual_organizations=sum(1 for o in orgs if o["organization_type"] == "individual"),
        firm_organizations=sum(1 for o in orgs if o["organization_type"] == "firm"),
        trial_organizations=sum(1 for o in orgs if o["subscription_status"] == "trial"),
        active_organizations=sum(1 for o in orgs if o["subscription_status"] == "active"),
        expired_organizations=sum(1 for o in orgs if o["subscription_status"] == "expired"),
        suspended_organizations=sum(1 for o in orgs if o["subscription_status"] == "suspended"),
        users_with_a_matter=len(users_with_a_matter),
        users_with_a_draft=len(users_with_a_draft),
        onboarding_funnel={
            "registered": len(trial_rows),
            "organization_created": len(
                {m["user_id"] for m in sc.table("memberships").select("user_id").execute().data}
            ),
            "first_matter_created": len(users_with_a_matter),
            "first_draft_generated": len(users_with_a_draft),
        },
    )


@router.get("/organizations", response_model=list[OrganizationListItemOut])
def list_organizations(
    status: str | None = Query(default=None),
    org_type: str | None = Query(default=None),
    _owner: CurrentUser = Depends(require_platform_owner),
):
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status filter: {status}")
    if org_type is not None and org_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid organization_type filter: {org_type}")

    sc = service_client()
    query = sc.table("organizations").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("subscription_status", status)
    if org_type:
        query = query.eq("organization_type", org_type)
    orgs = query.execute().data

    memberships = sc.table("memberships").select("organization_id").execute().data
    matters = sc.table("matters").select("organization_id").execute().data

    member_counts: dict[str, int] = {}
    for m in memberships:
        member_counts[m["organization_id"]] = member_counts.get(m["organization_id"], 0) + 1
    matter_counts: dict[str, int] = {}
    for m in matters:
        if m.get("organization_id"):
            matter_counts[m["organization_id"]] = matter_counts.get(m["organization_id"], 0) + 1

    return [
        OrganizationListItemOut(
            **org,
            member_count=member_counts.get(org["id"], 0),
            matter_count=matter_counts.get(org["id"], 0),
        )
        for org in orgs
    ]


@router.get("/organizations/{org_id}", response_model=OrganizationDetailOut)
def get_organization(org_id: str, _owner: CurrentUser = Depends(require_platform_owner)):
    sc = service_client()
    org_rows = sc.table("organizations").select("*").eq("id", org_id).limit(1).execute().data
    if not org_rows:
        raise HTTPException(status_code=404, detail="Organization not found")
    org = org_rows[0]

    membership_rows = sc.table("memberships").select("*").eq("organization_id", org_id).execute().data

    account_status_by_user: dict[str, str] = {}
    member_user_ids = [row["user_id"] for row in membership_rows]
    if member_user_ids:
        account_rows = (
            sc.table("account_security")
            .select("user_id,login_started_at,payment_received")
            .in_("user_id", member_user_ids)
            .execute()
            .data
        )
        account_row_by_user = {row["user_id"]: row for row in account_rows}
        account_status_by_user = {
            uid: _account_status(account_row_by_user.get(uid)) for uid in member_user_ids
        }

    members: list[MembershipOut] = []
    for row in membership_rows:
        email = None
        try:
            # Verified against the installed SDK (supabase 2.31.0 /
            # supabase_auth) during the 27 Aug 2026 security review:
            # SyncGoTrueAdminAPI.get_user_by_id(uid: str) -> UserResponse,
            # UserResponse.user.email is a real field. AuthApiError is the
            # specific exception this raises on a failed admin request
            # (user not found, network error, etc.) -- caught by name
            # rather than a bare `except Exception` so a genuinely
            # unexpected bug elsewhere in this loop still surfaces as a
            # 500 instead of silently degrading like a known, benign
            # lookup failure would.
            admin_user = sc.auth.admin.get_user_by_id(row["user_id"])
            email = admin_user.user.email
        except AuthApiError:
            # Best-effort enrichment only -- membership data itself
            # (role, join date) is still returned without it. Logged
            # (membership/user id only, never email or any token) so a
            # persistently failing admin lookup is observable rather than
            # silently always-None.
            logger.warning(
                "admin.get_user_by_id failed for membership_id=%s user_id=%s -- "
                "email enrichment degraded to None",
                row.get("id"), row.get("user_id"),
            )
        members.append(
            MembershipOut(**row, email=email, account_status=account_status_by_user.get(row["user_id"]))
        )

    org_matters = (
        sc.table("matters").select("module,created_at").eq("organization_id", org_id).execute().data
    )
    modules_used = sorted({m["module"] for m in org_matters if m.get("module")})
    last_activity_at = max((m["created_at"] for m in org_matters), default=None)

    return OrganizationDetailOut(
        **org,
        members=members,
        matter_count=len(org_matters),
        modules_used=modules_used,
        last_activity_at=last_activity_at,
    )


@router.patch("/organizations/{org_id}/access", response_model=OrganizationOut)
def update_organization_access(
    org_id: str,
    body: OrganizationAccessUpdate,
    owner: CurrentUser = Depends(require_platform_owner),
):
    sc = service_client()
    org_rows = sc.table("organizations").select("*").eq("id", org_id).limit(1).execute().data
    if not org_rows:
        raise HTTPException(status_code=404, detail="Organization not found")
    org = org_rows[0]
    previous_status = org["subscription_status"]

    update: dict[str, object] = {}
    if body.action == "mark_payment":
        # Option A (security review, 27 Aug 2026): this updates
        # ORGANIZATION-level state only. It does NOT touch
        # account_security.payment_received for any member of this
        # organization -- that remains a separate, per-user, hand-flipped
        # flag (Supabase Table Editor) that only Nitesh sets today. If a
        # member's own 5-day trial has separately expired, marking
        # organization payment here does not restore their access; you
        # must still flip their account_security row. See the frontend
        # Org Detail page for the same clarification shown to the owner,
        # and Enhancement_Roadmap.md / this session's review for why a
        # full consolidation (Option B) was deliberately deferred rather
        # than guessed at for firm memberships.
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "payment_marked_at": now,
            "payment_marked_by": owner.id,
            "access_enabled": True,
            "subscription_status": "active",
        }
    elif body.action == "enable":
        update = {"access_enabled": True, "subscription_status": "active"}
    elif body.action == "suspend":
        update = {"access_enabled": False, "subscription_status": "suspended"}
    elif body.action == "reactivate":
        update = {"access_enabled": True, "subscription_status": "active"}
    elif body.action == "extend_trial":
        days = body.extend_days or 5
        current_end = datetime.fromisoformat(org["trial_ends_at"].replace("Z", "+00:00"))
        base = max(current_end, datetime.now(timezone.utc))
        update = {
            "trial_ends_at": (base + timedelta(days=days)).isoformat(),
            "subscription_status": "trial",
            "access_enabled": True,
        }
    else:  # pragma: no cover — OrganizationAccessUpdate's Field pattern already rejects this
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")

    updated = sc.table("organizations").update(update).eq("id", org_id).execute().data[0]

    sc.table("organization_access_events").insert(
        {
            "organization_id": org_id,
            "previous_status": previous_status,
            "new_status": updated["subscription_status"],
            "action": body.action,
            "actor_user_id": owner.id,
            "reason": body.reason,
        }
    ).execute()

    return OrganizationOut(**updated)


@router.patch("/matters/{matter_id}/shared-demo", response_model=MatterOut)
def update_matter_shared_demo(
    matter_id: str,
    body: MatterDemoUpdate,
    owner: CurrentUser = Depends(require_platform_owner),
):
    """Flags/unflags a matter as a shared, read-only demo visible to every
    signed-in user across every organization -- see
    0030_shared_demo_matter_and_ecourts_allowlist.sql for the RLS side of
    this (additive SELECT-only policies on matters + its litigation
    satellite tables). Owner-only: this is a deliberate, narrow hole in
    tenant isolation, never something a matter's own organization can
    flip for itself."""
    sc = service_client()
    rows = sc.table("matters").select("id").eq("id", matter_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Matter not found")
    updated = (
        sc.table("matters")
        .update({"is_shared_demo": body.is_shared_demo})
        .eq("id", matter_id)
        .execute()
        .data[0]
    )
    return MatterOut(**updated)
