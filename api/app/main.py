import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

