"""Auth dependency: validates the caller's Supabase JWT and hands back a
per-request, RLS-scoped Supabase client (see db.py) so every query the
route makes is enforced by Postgres RLS as that user — never the service
role.

Authentication Logging Enhancement (2026-08-10): the Authentication
Investigation Sprint the same day found that this function previously
logged nothing on any rejection path — the only place a specific reason
(missing header vs. malformed vs. Supabase-rejected vs. session-revoked)
appeared was the HTTP response body, which Render's stdout capture does
not include (uvicorn's access log line records only the bare status
code). That made a real, one-off deploy-timing incident indistinguishable
from a persistent auth bug without a full live-testing pass. The logging
added below is purely diagnostic: every branch below raises the exact
same HTTPException with the exact same status/detail it always did —
only a WARNING-level, secret-free log line is new. Never logs the
Authorization header, the JWT, a refresh token, or any user PII (email/id)
— only a failure category, the request path, the HTTP status, a
high-level reason string, and a timestamp.

Raw exception visibility (2026-08-11): the category label alone (e.g.
"supabase_verification_failed") couldn't tell a Supabase-edge timeout
(httpx.ReadTimeout/ConnectError — a network problem) apart from a real
credential rejection (AuthApiError — an auth problem) — two failure
modes needing completely different fixes. For the one branch that wraps
an actual SDK exception (the anon_client().auth.get_user() call below),
_log_auth_failure() now also logs that exception's type and message
verbatim. Confirmed safe: neither httpx's connection exceptions nor
gotrue's AuthApiError embed the Authorization header or JWT value in
their message — the same str(exc) already goes into the HTTPException
detail returned to the caller.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Header, HTTPException, Request
from supabase import Client

from app.db import anon_client, user_client

logger = logging.getLogger("vidhidesk.auth")

# TEMP TIMING INSTRUMENTATION (Auth Request Forensics Sprint, latency
# follow-up, 2026-08-11): measures the auth.get_user() call in isolation
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


def _classify_supabase_exception(exc: Exception) -> tuple[str, str]:
    """Diagnostics-only classification of a Supabase auth SDK failure
    into (category, high-level reason) — never changes what's raised to
    the caller, only what's logged. The message substrings below were
    confirmed live against the real production Supabase project during
    the Authentication Investigation Sprint (2026-08-10): a structurally
    invalid token produces "...token is malformed: token contains an
    invalid number of segments"; a revoked/expired session produces the
    distinct "Session from session_id claim in JWT does not exist"."""
    text = str(exc).lower()
    if "malformed" in text or "invalid number of segments" in text or "unable to parse" in text:
        return "invalid_jwt", "token failed structural validation"
    if "session" in text and ("does not exist" in text or "expired" in text or "revoked" in text):
        return "session_expired_or_revoked", "session no longer valid at Supabase"
    return "supabase_verification_failed", "Supabase auth verification failed"


def _log_auth_failure(
    request: Request, category: str, status_code: int, reason: str,
    exc: Exception | None = None,
) -> None:
    """Structured, secret-free diagnostic logging for one authentication
    rejection. See module docstring for what is and is not logged.

    `exc`, when given, is the actual exception raised by the Supabase SDK
    call (not a local validation check) -- its raw type and message are
    logged alongside the mapped category. Added 2026-08-11: the category
    label alone (e.g. "supabase_verification_failed") was hiding whether
    a given failure was httpx timing out against Supabase's edge
    (httpx.ReadTimeout / httpx.ConnectError -- a network/latency problem)
    or Supabase cleanly rejecting the token (AuthApiError -- a real
    credential problem) -- two failure modes that need completely
    different fixes, previously indistinguishable from this log alone.
    Safe to log: neither httpx's connection exceptions nor gotrue's
    AuthApiError embed the Authorization header or JWT value in their
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


def get_current_user(request: Request, authorization: str = Header(...)) -> CurrentUser:
    if not authorization.lower().startswith("bearer "):
        _log_auth_failure(request, "malformed_header", 401, "missing 'Bearer ' prefix")
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        _log_auth_failure(request, "malformed_header", 401, "empty bearer token")
        raise HTTPException(status_code=401, detail="Missing bearer token")

    _t0 = time.perf_counter()
    try:
        resp = anon_client().auth.get_user(token)
    except Exception as exc:  # noqa: BLE001 — any auth SDK error means "not authenticated"
        _timing_logger.info(
            "timing auth.get_user duration_ms=%.1f outcome=error endpoint=%s",
            (time.perf_counter() - _t0) * 1000, request.url.path,
        )
        category, reason = _classify_supabase_exception(exc)
        _log_auth_failure(request, category, 401, reason, exc=exc)
        raise HTTPException(status_code=401, detail=f"Invalid session: {exc}") from exc
    _timing_logger.info(
        "timing auth.get_user duration_ms=%.1f outcome=ok endpoint=%s",
        (time.perf_counter() - _t0) * 1000, request.url.path,
    )

    if resp is None or resp.user is None:
        _log_auth_failure(request, "no_user_returned", 401, "Supabase returned no user for this token")
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    meta = getattr(resp.user, "user_metadata", None) or getattr(resp.user, "raw_user_meta_data", None)
    return CurrentUser(id=resp.user.id, email=resp.user.email, db=user_client(token), raw_user_meta_data=meta)

