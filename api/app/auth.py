"""Auth dependency: validates the caller's Supabase JWT and hands back a
per-request, RLS-scoped Supabase client (see db.py) so every query the
route makes is enforced by Postgres RLS as that user — never the service
role.

Authentication Logging Enhancement (2026-08-10): the Authentication
Investigation Sprint the same day found that this function previously
logged nothing on any rejection path — the only place a specific reason
(missing header vs. malformed vs. rejected vs. session-revoked) appeared
was the HTTP response body, which Render's stdout capture does not
include (uvicorn's access log line records only the bare status code).
That made a real, one-off deploy-timing incident indistinguishable from a
persistent auth bug without a full live-testing pass. The logging added
below is purely diagnostic: every branch below raises the exact same
HTTPException with the exact same status/detail it always did — only a
WARNING-level, secret-free log line is new. Never logs the Authorization
header, the JWT, a refresh token, or any user PII (email/id) — only a
failure category, the request path, the HTTP status, a high-level reason
string, and a timestamp.

Local JWT verification (Auth Request Forensics Sprint, 2026-08-13): this
function previously called Supabase Auth's remote auth.get_user() on
every single request via async_anon_client(). Production timing logs
showed that call taking 20-64s under load — well past the frontend's 12s
FETCH_TIMEOUT_MS — while a direct forensic query against the database via
service_client() confirmed the DB itself (public.templates,
public.matters) was healthy and fast. That isolated the bottleneck to
this remote verification call specifically.

This project's Supabase Auth signing key is ES256 (asymmetric — confirmed
live against this project's JWKS endpoint), so the JWT is now verified
locally against that JWKS (signature, expiry, issuer, audience, presence
of `sub`) via PyJWT + jwt.PyJWKClient (see app/db.py::jwks_client()) —
zero outbound network call on the normal request path. auth.get_user() is
no longer called here at all; _classify_jwt_exception() below replaces
the old Supabase-SDK exception classifier with one for PyJWT's exception
types. Never logs the Authorization header, the JWT, or any signing key
material — only a failure category, the request path, the HTTP status, a
high-level reason string, and (same as before) the exception's own
type/message, which PyJWT's exceptions do not embed key material in.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Request
from supabase import Client

from app.config import get_settings
from app.db import jwks_client, service_client, user_client

# Supabase Auth issues ES256-signed access tokens with a fixed, well-known
# `aud` for any signed-in user. Both are asserted explicitly (rather than
# trusting whatever the token claims) so a token signed by a different
# issuer/audience — even if it somehow carried a valid signature from
# *some* key — is still rejected. `algorithms` is likewise an explicit
# allow-list, not read from the token's own header, which is what closes
# off the classic "attacker picks the algorithm" confusion class of bug.
SUPABASE_JWT_ALGORITHMS = ["ES256"]
SUPABASE_JWT_AUDIENCE = "authenticated"

# Wall-clock ceiling on the whole verification step (normally in-memory/
# instant; only a JWKS cache-miss fetch touches the network at all).
AUTH_WALL_CLOCK_TIMEOUT_S = 4.0

logger = logging.getLogger("vidhidesk.auth")

# Free-trial paywall: a new sign-up gets this many days of full access from
# their FIRST-EVER /api/auth/session-start call (app/routers/auth.py) --
# that timestamp is written once and never overwritten on later logins (see
# that router's docstring), so repeatedly signing out/in does not extend
# the trial. Past the window, every other endpoint rejects the request with
# 401 TRIAL_EXPIRED -- permanently, UNLESS `payment_received` has been
# flipped to true for that user (Nitesh does this by hand in the Supabase
# Table Editor after receiving payment; see migrations/0023_account_autolock_payment_toggle.sql),
# in which case access is unlocked forever and this check is skipped
# entirely, with no need to sign in again.
TRIAL_WINDOW = timedelta(days=5)

# The one endpoint allowed to run past the trial window -- it's the
# endpoint that records the trial's start, so it can't be gated by the
# thing it initializes (a first-ever caller has no row yet to check).
# Shared by both _check_account_not_locked and _check_organization_access
# below -- session-start is where organization provisioning happens too,
# so it can't be gated by the thing it provisions either.
_AUTH_GATE_EXEMPT_PATHS = frozenset({"/api/auth/session-start"})

# Row-per-user table, so this in-process cache stays small even with many
# trial sign-ups. TTL keeps the trial check off the per-request Postgrest
# round trip without materially loosening the 5-day boundary or delaying a
# payment-received unlock by more than this long -- see
# _check_account_not_locked().
_ACCOUNT_LOCK_CACHE_TTL_S = 60.0


@dataclass
class _TrialState:
    login_started_at: datetime | None
    payment_received: bool


_account_lock_cache: dict[str, tuple[float, _TrialState]] = {}

_NO_TRIAL_ROW_YET = _TrialState(login_started_at=None, payment_received=False)


def _fetch_trial_state_sync(user_id: str) -> _TrialState:
    """Blocking Supabase call -- always run via asyncio.to_thread() (see
    _fetch_trial_state()), never awaited directly from an `async def`, for
    the same event-loop-blocking reason _verify_jwt_locally() above is
    offloaded rather than called inline."""
    res = (
        service_client()
        .table("account_security")
        .select("login_started_at,payment_received")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return _NO_TRIAL_ROW_YET
    row = res.data[0]
    return _TrialState(
        login_started_at=datetime.fromisoformat(row["login_started_at"].replace("Z", "+00:00")),
        payment_received=bool(row["payment_received"]),
    )


async def _fetch_trial_state(user_id: str) -> _TrialState:
    now_monotonic = time.monotonic()
    cached = _account_lock_cache.get(user_id)
    if cached is not None and (now_monotonic - cached[0]) < _ACCOUNT_LOCK_CACHE_TTL_S:
        return cached[1]

    try:
        state = await asyncio.wait_for(
            asyncio.to_thread(_fetch_trial_state_sync, user_id),
            timeout=AUTH_WALL_CLOCK_TIMEOUT_S,
        )
    except Exception:
        # Fail open: a Supabase hiccup or slow response should not block a
        # paying (or still-in-trial) user. Not cached, so the next request
        # retries rather than pinning the outage for the full TTL.
        logger.warning("account_security lookup failed; failing open", exc_info=True)
        return cached[1] if cached is not None else _NO_TRIAL_ROW_YET

    _account_lock_cache[user_id] = (now_monotonic, state)
    return state


async def _check_account_not_locked(request: Request, user_id: str) -> None:
    if request.url.path in _AUTH_GATE_EXEMPT_PATHS:
        return
    state = await _fetch_trial_state(user_id)
    if state.payment_received:
        return
    if state.login_started_at is None:
        # No session-start row yet (e.g. a session that predates this
        # feature). Nothing to enforce until the next real login records one.
        return
    if datetime.now(timezone.utc) - state.login_started_at > TRIAL_WINDOW:
        _log_auth_failure(request, "trial_expired", 401, "5-day free trial window exceeded")
        raise HTTPException(
            status_code=401,
            detail="TRIAL_EXPIRED: your 5-day free trial has ended. Please arrange payment to continue.",
        )


# Organization resolution (Enhancement_Roadmap.md §3 Tenant Foundation):
# a user's organization_id, looked up via memberships (0024_tenant_foundation.sql)
# and attached to CurrentUser so every router can set it on INSERT without
# its own Supabase round trip. Same in-process TTL-cache shape as
# _fetch_trial_state above -- a stale org_id for up to this many seconds
# is harmless (membership changes are rare and admin-driven), and failing
# open here (returning None) is deliberate: RLS's WITH CHECK on
# organization_id IS NOT NULL is the actual enforcement, so a lookup
# hiccup produces a clean 4xx from the insert itself, not a silent bypass.
_ORG_ID_CACHE_TTL_S = 60.0
_org_id_cache: dict[str, tuple[float, str | None]] = {}


def _fetch_organization_id_sync(user_id: str) -> str | None:
    # Deterministic by construction (security review follow-up, 27 Aug
    # 2026): the schema permits a user to belong to more than one
    # organization (future firm-collaboration support), so this filters
    # on is_default rather than taking an arbitrary row via a bare
    # LIMIT 1. Exactly one membership per user may have is_default=true,
    # enforced by a partial unique index
    # (idx_memberships_one_default_per_user, 0024_tenant_foundation.sql),
    # not just by this query's intent.
    res = (
        service_client()
        .table("memberships")
        .select("organization_id")
        .eq("user_id", user_id)
        .eq("is_default", True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return res.data[0]["organization_id"]


class _AuthorizationLookupFailed(Exception):
    """Raised when a Supabase lookup needed to make an authorization
    decision (organization membership or organization access state)
    could not be completed -- deliberately distinct from a *successful*
    lookup that determines "no membership exists". Round 2 of the
    security review (27 Aug 2026) found the first version of this gate
    treated both cases as an implicit allow (fail open). That is exactly
    backwards for an authorization boundary: an inability to verify a
    requirement must never become an implicit grant of it. Every raiser
    of this exception is caught in _check_organization_access and turned
    into a controlled 503 -- the underlying infrastructure error (network,
    Supabase outage, malformed response) is logged, never returned to the
    caller."""


async def _fetch_organization_id(user_id: str) -> str | None:
    """Returns this user's default organization_id, or None if they
    genuinely have no default membership (a real, successfully-determined
    result -- not a failure). Raises _AuthorizationLookupFailed if the
    lookup itself could not be completed. A cache HIT is still an
    unconditional fast path (a recent successful lookup remains valid for
    its TTL); only a cache MISS that then fails raises -- it never falls
    back to a stale cached value as a substitute for a fresh failed
    check, which is precisely the fail-open behavior being removed here."""
    now_monotonic = time.monotonic()
    cached = _org_id_cache.get(user_id)
    if cached is not None and (now_monotonic - cached[0]) < _ORG_ID_CACHE_TTL_S:
        return cached[1]

    try:
        org_id = await asyncio.wait_for(
            asyncio.to_thread(_fetch_organization_id_sync, user_id),
            timeout=AUTH_WALL_CLOCK_TIMEOUT_S,
        )
    except Exception as exc:
        logger.warning("membership lookup failed; cannot verify organization membership", exc_info=True)
        raise _AuthorizationLookupFailed("membership lookup failed") from exc

    _org_id_cache[user_id] = (now_monotonic, org_id)
    return org_id


# Organization access gate (security review follow-up, 27 Aug 2026,
# rewritten fail-closed in round 2 the same day). ADDITIVE to
# _check_account_not_locked above, never a replacement for it. The
# effective rule per-request is:
#
#   account_security allows this user
#   AND organization membership is verified (not just "unknown")
#   AND organization access is verified enabled
#
# checked in that exact order (see get_current_user below) so an expired
# user-level trial always surfaces as 401 TRIAL_EXPIRED even if their
# organization is also suspended -- existing semantics for that response
# are preserved byte-for-byte; this gate never runs, let alone overrides
# it, until the trial check has already passed.
#
# Three distinct outcomes, never conflated:
#   - 403 ORG_MEMBERSHIP_REQUIRED -- authenticated, but no valid default
#     organization membership exists (or it points at an organization row
#     that no longer exists). A session that predates provisioning
#     finishing legitimately hits this for the brief window before
#     routers/auth.py::_ensure_organization completes -- that is a real,
#     if usually momentary, "not yet authorized" state, not something to
#     paper over by allowing the request through.
#   - 503 AUTHORIZATION_UNAVAILABLE -- the lookup itself failed
#     (Supabase outage, network error, timeout). Never exposes the raw
#     infrastructure error; the request is denied, not allowed, because
#     an authorization requirement could not be verified.
#   - 403 ORG_ACCESS_DISABLED -- membership and organization both
#     resolved successfully, but access_enabled=false or
#     subscription_status is suspended/expired.
@dataclass
class _OrgAccessState:
    access_enabled: bool
    subscription_status: str


_ORG_ACCESS_CACHE_TTL_S = 60.0
_org_access_cache: dict[str, tuple[float, _OrgAccessState | None]] = {}

_ORG_ACCESS_DENYING_STATUSES = frozenset({"suspended", "expired"})

_ORG_MEMBERSHIP_REQUIRED_DETAIL = (
    "ORG_MEMBERSHIP_REQUIRED: this account is not linked to a valid organization. "
    "Please sign out and sign in again, or contact your platform administrator."
)
_AUTHORIZATION_UNAVAILABLE_DETAIL = (
    "AUTHORIZATION_UNAVAILABLE: unable to verify organization access right now. "
    "Please try again shortly."
)


def _fetch_org_access_state_sync(organization_id: str) -> _OrgAccessState | None:
    res = (
        service_client()
        .table("organizations")
        .select("access_enabled,subscription_status")
        .eq("id", organization_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    return _OrgAccessState(
        access_enabled=bool(row["access_enabled"]),
        subscription_status=row["subscription_status"],
    )


async def _fetch_org_access_state(organization_id: str) -> _OrgAccessState | None:
    """Returns the organization's access state, or None if the row
    genuinely does not exist (a real result -- the membership points at a
    nonexistent organization). Raises _AuthorizationLookupFailed if the
    lookup could not be completed -- same cache-hit-is-still-a-fast-path,
    no-stale-fallback-on-a-failed-miss posture as _fetch_organization_id."""
    now_monotonic = time.monotonic()
    cached = _org_access_cache.get(organization_id)
    if cached is not None and (now_monotonic - cached[0]) < _ORG_ACCESS_CACHE_TTL_S:
        return cached[1]

    try:
        state = await asyncio.wait_for(
            asyncio.to_thread(_fetch_org_access_state_sync, organization_id),
            timeout=AUTH_WALL_CLOCK_TIMEOUT_S,
        )
    except Exception as exc:
        logger.warning("organizations lookup failed; cannot verify organization access", exc_info=True)
        raise _AuthorizationLookupFailed("organization access lookup failed") from exc

    _org_access_cache[organization_id] = (now_monotonic, state)
    return state


async def _check_organization_access(request: Request, user_id: str) -> str | None:
    """Resolves AND verifies organization membership/access in one pass.
    Returns the verified organization_id (to populate CurrentUser) on
    success, or None only for an exempt path. Every other outcome either
    returns a real organization_id or raises -- there is no path back to
    the caller that means "couldn't tell, allow anyway"."""
    if request.url.path in _AUTH_GATE_EXEMPT_PATHS:
        return None

    try:
        organization_id = await _fetch_organization_id(user_id)
    except _AuthorizationLookupFailed:
        _log_auth_failure(
            request, "authorization_unavailable", 503,
            "organization membership lookup failed",
        )
        raise HTTPException(status_code=503, detail=_AUTHORIZATION_UNAVAILABLE_DETAIL)

    if organization_id is None:
        _log_auth_failure(request, "org_membership_required", 403, "no default organization membership")
        raise HTTPException(status_code=403, detail=_ORG_MEMBERSHIP_REQUIRED_DETAIL)

    try:
        state = await _fetch_org_access_state(organization_id)
    except _AuthorizationLookupFailed:
        _log_auth_failure(
            request, "authorization_unavailable", 503,
            "organization access-state lookup failed",
        )
        raise HTTPException(status_code=503, detail=_AUTHORIZATION_UNAVAILABLE_DETAIL)

    if state is None:
        # Membership row exists but points at an organization that
        # doesn't (a data-integrity edge case, not a normal user path --
        # organizations are never deleted by any code in this app today).
        # Treated the same as "no valid membership", never as "allow".
        _log_auth_failure(request, "org_membership_required", 403, "membership references a nonexistent organization")
        raise HTTPException(status_code=403, detail=_ORG_MEMBERSHIP_REQUIRED_DETAIL)

    if not state.access_enabled or state.subscription_status in _ORG_ACCESS_DENYING_STATUSES:
        _log_auth_failure(
            request, "org_access_disabled", 403,
            f"organization access disabled (status={state.subscription_status})",
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "ORG_ACCESS_DISABLED: your organization currently does not have access to "
                "VidhiDesk. Please contact your platform administrator."
            ),
        )

    return organization_id


# TEMP TIMING INSTRUMENTATION (Auth Request Forensics Sprint, latency
# follow-up, 2026-08-11): measures the auth verification step in isolation
# so it can be compared against the table(...).execute() timing in
# app/routers/matters.py and the total-request timing in app/main.py --
# together they show where a request's time is actually going. Remove
# once the sprint's before/after comparison is done.
_timing_logger = logging.getLogger("vidhidesk.timing")


@dataclass
class CurrentUser:
    id: str
    email: str | None
    db: Client
    raw_user_meta_data: dict | None = None
    organization_id: str | None = None


def _classify_jwt_exception(exc: Exception) -> tuple[str, str]:
    """Diagnostics-only classification of a local JWT verification failure
    into (category, high-level reason) — never changes what's raised to
    the caller, only what's logged. Replaces the old Supabase-SDK
    exception classifier (2026-08-13, local JWT verification) now that
    verification happens via PyJWT against this project's JWKS instead of
    a remote auth.get_user() call."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "jwks_fetch_timeout", "JWKS endpoint did not respond in time"
    if isinstance(exc, jwt.ExpiredSignatureError):
        return "jwt_expired", "JWT has expired"
    if isinstance(exc, jwt.InvalidSignatureError):
        return "invalid_jwt_signature", "JWT signature verification failed"
    if isinstance(exc, jwt.InvalidAudienceError):
        return "invalid_jwt_audience", "JWT audience did not match this project"
    if isinstance(exc, jwt.InvalidIssuerError):
        return "invalid_jwt_issuer", "JWT issuer did not match this project"
    if isinstance(exc, jwt.MissingRequiredClaimError):
        return "invalid_jwt_claims", "JWT is missing a required claim (exp/sub)"
    if isinstance(exc, jwt.exceptions.PyJWKClientError):
        return "jwks_lookup_failed", "no matching signing key found in this project's JWKS"
    if isinstance(exc, jwt.PyJWTError):
        return "invalid_jwt", "token failed structural or cryptographic validation"
    return "jwt_verification_error", "unexpected error during local JWT verification"


def _log_auth_failure(
    request: Request, category: str, status_code: int, reason: str,
    exc: Exception | None = None,
) -> None:
    """Structured, secret-free diagnostic logging for one authentication
    rejection. See module docstring for what is and is not logged.

    `exc`, when given, is the actual exception raised during local JWT
    verification (jwt.decode() / jwks_client() -- not a local structural
    check) -- its raw type and message are logged alongside the mapped
    category. Added 2026-08-11, updated 2026-08-13 for local JWT
    verification: the category label alone (e.g. "invalid_jwt") was
    hiding whether a given failure was the JWKS endpoint timing out (a
    network/latency problem) or the token itself being cryptographically
    rejected (a real credential problem) -- two failure modes that need
    completely different fixes, previously indistinguishable from this
    log alone. Safe to log: PyJWT's exceptions do not embed the
    Authorization header, JWT value, or any signing key material in their
    message -- confirmed by the fact the exact same str(exc) already goes
    into the HTTPException detail returned to the caller below."""
    exc_type = f"{type(exc).__module__}.{type(exc).__name__}" if exc is not None else "n/a"
    exc_message = str(exc) if exc is not None else "n/a"
    logger.warning(
        "auth.get_current_user auth_failure category=%s endpoint=%s status=%d reason=%s "
        "exc_type=%s exc_message=%s timestamp=%s",
        category, request.url.path, status_code, reason,
        exc_type, exc_message, datetime.now(timezone.utc).isoformat(),
    )


def _verify_jwt_locally(token: str) -> dict:
    """Cryptographically verify `token` against this project's JWKS
    (ES256, asymmetric) — signature, expiry, issuer, audience, presence of
    `sub` — with no remote Supabase Auth call. Runs on a worker thread via
    asyncio.to_thread() since PyJWKClient's HTTP fetch (only hit on a JWKS
    cache miss/rotation, see app/db.py::jwks_client()) is synchronous.
    Raises a jwt.PyJWTError subclass on any failure; see
    _classify_jwt_exception() for how each is categorized for logging."""
    settings = get_settings()
    signing_key = jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=SUPABASE_JWT_ALGORITHMS,
        audience=SUPABASE_JWT_AUDIENCE,
        issuer=f"{settings.supabase_url}/auth/v1",
        options={"require": ["exp", "sub"]},
    )


async def get_current_user(request: Request, authorization: str = Header(...)) -> CurrentUser:
    if not authorization.lower().startswith("bearer "):
        _log_auth_failure(request, "malformed_header", 401, "missing 'Bearer ' prefix")
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        _log_auth_failure(request, "malformed_header", 401, "empty bearer token")
        raise HTTPException(status_code=401, detail="Missing bearer token")

    _t0 = time.perf_counter()
    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(_verify_jwt_locally, token),
            timeout=AUTH_WALL_CLOCK_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — any verification error or timeout means "not authenticated"
        _timing_logger.info(
            "timing auth.local_jwt_verify duration_ms=%.1f outcome=error endpoint=%s",
            (time.perf_counter() - _t0) * 1000, request.url.path,
        )
        category, reason = _classify_jwt_exception(exc)
        _log_auth_failure(request, category, 401, reason, exc=exc)
        raise HTTPException(status_code=401, detail=f"Invalid session: {exc}") from exc
    _timing_logger.info(
        "timing auth.local_jwt_verify duration_ms=%.1f outcome=ok endpoint=%s",
        (time.perf_counter() - _t0) * 1000, request.url.path,
    )

    sub = payload.get("sub")
    if not sub:
        _log_auth_failure(request, "no_user_returned", 401, "JWT verified but carried no sub claim")
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    await _check_account_not_locked(request, sub)
    organization_id = await _check_organization_access(request, sub)

    return CurrentUser(
        id=sub,
        email=payload.get("email"),
        db=user_client(token),
        raw_user_meta_data=payload.get("user_metadata"),
        organization_id=organization_id,
    )


def require_platform_owner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency gating every /api/platform/* route (Enhancement_Roadmap.md
    §4/§17). Compares the caller's email against PLATFORM_OWNER_EMAILS --
    never a value the client supplies, only the `email` claim already
    cryptographically verified in get_current_user() above. This is the
    single, maintainable owner-check mechanism the spec asks for; do not
    duplicate this comparison elsewhere -- import and depend on this
    function instead. A non-owner gets a plain 403, matching principle #17
    ("ordinary authenticated users must receive 403 ... from owner-only
    APIs"), not a redirect or a UI-only block.
    """
    allowed = {
        e.strip().lower()
        for e in get_settings().platform_owner_emails.split(",")
        if e.strip()
    }
    if not user.email or user.email.strip().lower() not in allowed:
        raise HTTPException(status_code=403, detail="Platform owner access required")
    return user


