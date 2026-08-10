import logging

from fastapi import FastAPI
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

