import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import citations, contracts, health, litigation, matters, profile, retrieval

# Sprint 3.6 Phase 4 (TICKET-22): with no handler configured, Python's
# logging module falls back to its "handler of last resort," which only
# ever surfaces WARNING and above — every module's logger.info() call
# (llm_gateway's successful-generation line included) was silently
# discarded in every real run, confirmed during the Sprint 3.5.6
# certification round (52 WARNING-level failure lines captured, 0
# INFO-level success lines, despite 26 real successful generations).
# vidhidesk.* loggers specifically, not the root logger wholesale, so
# third-party library verbosity (httpx, uvicorn's own access log, etc.)
# is unaffected.
logging.getLogger("vidhidesk").setLevel(logging.INFO)
if not logging.getLogger("vidhidesk").handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logging.getLogger("vidhidesk").addHandler(_handler)

app = FastAPI(title="VidhiDesk API", version="0.1.0")

settings = get_settings()

# Prepare clean CORS origins list, excluding wildcard strings which break credentialed requests
raw_origins = settings.cors_origins if isinstance(settings.cors_origins, list) else [settings.cors_origins]
cors_origins = [str(o).strip().rstrip("/") for o in raw_origins if o and str(o).strip() != "*"]

# Ensure default production and local origins are present
default_origins = ["http://localhost:3000", "https://vidhidesk.vercel.app"]
for default_origin in default_origins:
    if default_origin not in cors_origins:
        cors_origins.append(default_origin)

_error_logger = logging.getLogger("vidhidesk.errors")


# Auth Request Forensics Sprint (2026-08-11): registered BEFORE
# add_middleware(CORSMiddleware) below -- Starlette's add_middleware()
# inserts at the front of the middleware list, so whatever is registered
# LAST ends up OUTERMOST. Registering this first means it ends up
# innermost (right next to routing), so CORSMiddleware wraps it and still
# gets a chance to attach CORS headers to whatever it returns.
#
# This matters because an unhandled (non-HTTPException) exception raised
# inside a route -- e.g. a Supabase client call with no try/except --
# propagates all the way out to Starlette's ServerErrorMiddleware, which
# sits OUTSIDE CORSMiddleware and sends its fallback 500 on the raw ASGI
# `send`, bypassing CORSMiddleware's header injection entirely. The
# browser then reports that response as "blocked by CORS policy: No
# Access-Control-Allow-Origin header present" -- CORS is configured
# correctly, but the error response never passed through it. Verified
# locally with an isolated TestClient repro (identical CORSMiddleware
# config): an unhandled RuntimeError produced a 500 with zero CORS
# headers; the same exception caught here and turned into a JSONResponse
# came back with the correct headers. A top-level
# @app.exception_handler(Exception) does NOT fix this -- it's routed
# through the same outer ServerErrorMiddleware and was verified to still
# strip CORS headers.
@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        _error_logger.exception("unhandled_exception endpoint=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


_timing_logger = logging.getLogger("vidhidesk.timing")


# TEMP TIMING INSTRUMENTATION (Auth Request Forensics Sprint, latency
# follow-up, 2026-08-11): total wall-clock time for every request, to be
# read alongside the auth.get_user() timing (app/auth.py) and
# table(...).execute() timing (app/routers/matters.py) -- together they
# show where a request's time actually goes. Added AFTER
# catch_unhandled_exceptions above, so (per the ordering note on that
# middleware) it ends up OUTER relative to it -- this measures the full
# request including exception-recovery time, not just the happy path.
# Remove once the sprint's before/after comparison is done.
@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    _timing_logger.info(
        "timing total_request duration_ms=%.1f path=%s method=%s status=%d",
        (time.perf_counter() - start) * 1000, request.url.path, request.method, response.status_code,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*vidhidesk.*\.vercel\.app|https://vidhidesk\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "VidhiDesk API",
        "notice": "AI-generated draft for advocate review. Not legal advice.",
    }


app.include_router(health.router)
app.include_router(matters.router)
app.include_router(litigation.router)
app.include_router(citations.router)
app.include_router(retrieval.router)
app.include_router(contracts.router)
app.include_router(profile.router)

_auth_logger = logging.getLogger("vidhidesk.auth")


# Authentication Logging Enhancement (2026-08-10): a genuinely MISSING
# Authorization header never reaches app/auth.py::get_current_user at
# all — FastAPI's own required-header validation (Header(...)) rejects
# it first, with a 422, before the dependency body ever runs. This is
# the one failure category that has to be logged from here instead.
# This handler changes NOTHING about the response: it always delegates
# to FastAPI's own default request_validation_exception_handler, so the
# status code and body are byte-identical to before this change — it
# only adds a WARNING-level, secret-free log line, and only for the
# specific case of a missing `authorization` header (every other
# validation error in the app is unaffected and logs nothing new).
@app.exception_handler(RequestValidationError)
async def _log_missing_auth_header(request: Request, exc: RequestValidationError):
    for err in exc.errors():
        loc = err.get("loc", ())
        if len(loc) >= 2 and loc[0] == "header" and loc[1] == "authorization":
            _auth_logger.warning(
                "auth.get_current_user auth_failure category=%s endpoint=%s status=%d reason=%s timestamp=%s",
                "missing_header", request.url.path, 422, "Authorization header not provided",
                datetime.now(timezone.utc).isoformat(),
            )
            break
    return await request_validation_exception_handler(request, exc)

