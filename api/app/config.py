from functools import lru_cache
import json

from dotenv import find_dotenv, load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo layout: env vars live in the monorepo-root .env, not /api/.env.
# find_dotenv walks up from cwd so this works whether uvicorn is launched
# from /api or from the repo root.
load_dotenv(find_dotenv(usecwd=True))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Indian Kanoon
    indian_kanoon_api_token: str = ""

    # LLM providers — failover order per CLAUDE.md Decision 3
    gemini_api_key: str = ""
    groq_api_key: str = ""
    sambanova_api_key: str = ""
    cerebras_api_key: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://vidhidesk.vercel.app",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str] | None) -> list[str]:
        if v is None:
            return ["http://localhost:3000", "https://vidhidesk.vercel.app"]
        if isinstance(v, str):
            v_str = v.strip()
            if not v_str:
                return ["http://localhost:3000", "https://vidhidesk.vercel.app"]
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if item]
                except Exception:
                    pass
            if "," in v_str:
                return [item.strip() for item in v_str.split(",") if item.strip()]
            return [v_str]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()

