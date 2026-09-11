"""eCourts search allowlist (2026-09-11): gates any operation that can
trigger a live, billable eCourts API call (see court_data_gateway.py) to
callers whose email is in public.ecourts_search_allowlist. Requested
directly by the platform owner: the app pays per eCourts call, and every
new sign-up must NOT be able to burn that quota by default -- only
emails explicitly added to this table can.

Deliberately a Supabase-managed table, not an env var like
PLATFORM_OWNER_EMAILS (app/auth.py::require_platform_owner) -- the owner
asked for this to be editable straight from the Supabase table editor
(e.g. to admit a specific "authorised tester" later) without a redeploy.
0030_shared_demo_matter_and_ecourts_allowlist.sql seeds it with the
owner's own email so nothing regresses for him.

Same cache-hit-is-a-fast-path, fail-closed-on-a-failed-lookup posture as
app/auth.py's _fetch_organization_id/_fetch_org_access_state: a lookup
failure must never silently allow a live paid call through -- it defaults
to "not allowed" and logs, rather than either caching a false positive or
raising a 5xx that would itself be confusing on a feature this minor.
"""

from __future__ import annotations

import logging
import time

from app.db import service_client

logger = logging.getLogger("vidhidesk.ecourts_access")

_ALLOWLIST_CACHE_TTL_S = 60.0
_allowlist_cache: tuple[float, frozenset[str]] | None = None

# Frontend-facing marker (see web/src/lib/api.ts) so the UI can show a
# polite, specific notice instead of a raw "System Error" -- same pattern
# as ORG_MEMBERSHIP_REQUIRED/ORG_ACCESS_DISABLED in app/auth.py.
ECOURTS_SEARCH_RESTRICTED_DETAIL = (
    "ECOURTS_SEARCH_RESTRICTED: Looking up a new CNR is limited to the "
    "platform owner during testing, to control eCourts API costs. You're "
    "welcome to verify any case number shown in the app directly at "
    "https://services.ecourts.gov.in/ -- that's free and always available."
)


def _fetch_allowlist_sync() -> frozenset[str]:
    res = service_client().table("ecourts_search_allowlist").select("email").execute()
    return frozenset(
        row["email"].strip().lower() for row in (res.data or []) if row.get("email")
    )


def is_ecourts_search_allowed(email: str | None) -> bool:
    """True only if `email` is on the live allowlist. Never raises --
    a lookup failure is logged and treated as "not allowed", the safe
    default for a cost-control gate."""
    global _allowlist_cache
    if not email:
        return False

    now = time.monotonic()
    if _allowlist_cache is not None and (now - _allowlist_cache[0]) < _ALLOWLIST_CACHE_TTL_S:
        allowed = _allowlist_cache[1]
    else:
        try:
            allowed = _fetch_allowlist_sync()
        except Exception:
            logger.warning("ecourts allowlist lookup failed; defaulting to deny", exc_info=True)
            allowed = frozenset()
        _allowlist_cache = (now, allowed)

    return email.strip().lower() in allowed
