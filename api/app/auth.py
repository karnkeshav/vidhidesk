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
from datetime import datetime, timezone

import jwt
from fastapi import Header, HTTPException, Request
from supabase import Client

from app.config import get_settings
from app.db import jwks_client, user_client

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

    return CurrentUser(
        id=sub,
        email=payload.get("email"),
        db=user_client(token),
        raw_user_meta_data=payload.get("user_metadata"),
    )


