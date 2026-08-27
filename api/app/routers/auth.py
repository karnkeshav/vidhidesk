"""Free-trial session-start endpoint.

Called by the frontend once, right after a sign-in completes
(web/src/app/login/page.tsx -- both the no-MFA and the post-TOTP paths,
never on a plain page load/session restore). Records the moment this
user's 5-day free trial started -- app/auth.py::_check_account_not_locked
enforces that window on every other authenticated request, unless
`payment_received` has been flipped to true.

Deliberately insert-once: the trial start must NOT move just because the
advocate signs out and back in, or the "5 days free" promise becomes "5
days free, resettable forever." A duplicate call (every login after the
first) hits the table's user_id primary key and is silently ignored --
see migrations/0022_account_autolock.sql / 0023_account_autolock_payment_toggle.sql
for why the authenticated role has no INSERT/UPDATE policy on this table
at all (writes only via service_client() here).

Also the onboarding hook for Tenant Foundation (Enhancement_Roadmap.md
§3, migration 0024_tenant_foundation.sql): a brand-new user with no
membership row yet gets one individual organization + an org_admin
membership created here, via the atomic
public.ensure_organization_membership() Postgres function
(0024_tenant_foundation.sql Section 5b) -- not the account_security
trial mechanism itself, which is deliberately left untouched (see this
session's discussion). The new organization starts subscription_status
='trial' (its DEFAULT); as of 27 Aug 2026 this DOES gate requests --
app/auth.py::_check_organization_access -- as a second, additive check
alongside (never replacing) account_security's own enforcement.

Provisioning is a single RPC call rather than the two separate
INSERTs this file used before 27 Aug 2026: that version could leave an
orphaned organization (created, but never linked to a membership) if the
process crashed or the connection dropped between the two calls. The
Postgres function is atomic (one function body, one transaction) and
concurrency-safe (an advisory lock keyed by the user's own id serializes
two simultaneous first-ever calls for the SAME user, e.g. two browser
tabs signing in at once) -- see the function's own comment for detail.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError

from app.auth import CurrentUser, get_current_user
from app.db import service_client

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("vidhidesk.auth")

# Postgres unique_violation SQLSTATE -- the expected, benign outcome of
# every login after the first (the user_id primary key already has a row).
_UNIQUE_VIOLATION = "23505"


def _ensure_organization(user: CurrentUser) -> None:
    """Provision (or resolve) this user's default organization via the
    atomic ensure_organization_membership() RPC. Best-effort with respect
    to sign-in itself -- a failure here must not block the user from
    reaching /dashboard, same posture as login/page.tsx's own
    startSession().catch(() => {}) -- but unlike the previous
    implementation, a failure is now LOGGED, not silently discarded: an
    organization that never got provisioned is observable (this warning,
    carrying only the user id -- never email, never any request/response
    body) rather than a user who mysteriously can't create a matter days
    later with no trail explaining why."""
    try:
        service_client().rpc(
            "ensure_organization_membership",
            {"p_user_id": user.id, "p_email": user.email},
        ).execute()
    except Exception:
        logger.warning(
            "ensure_organization_membership RPC failed for user_id=%s -- "
            "organization provisioning incomplete, matter/hearing creation "
            "will 400 until this is retried or repaired",
            user.id,
            exc_info=True,
        )


@router.post("/session-start")
def start_session(user: CurrentUser = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    try:
        service_client().table("account_security").insert(
            {"user_id": user.id, "login_started_at": now, "updated_at": now}
        ).execute()
    except APIError as exc:
        if getattr(exc, "code", None) != _UNIQUE_VIOLATION:
            raise
    _ensure_organization(user)
    return {"status": "ok"}
