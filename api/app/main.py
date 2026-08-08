from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import citations, contracts, health, litigation, matters, profile, retrieval

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

