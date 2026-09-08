from functools import lru_cache
import json

from dotenv import find_dotenv, load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo layout: env vars live in the monorepo-root .env, not /api/.env.
# find_dotenv walks up from cwd so this works whether uvicorn is launched
# from /api or from the repo root.
load_dotenv(find_dotenv(usecwd=True))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Indian Kanoon
    indian_kanoon_api_token: str = ""

    # eCourtsIndia — read by app/services/court_data_gateway.py
    # (docs/00_Product/Enhancement_Roadmap.md §4).
    ecourts_api_key: str = ""

    # Sync window configuration (spec Section 8: "do not hardcode
    # production timing unnecessarily") -- read by
    # scripts/court_sync_scheduler.py. Defaults target the evening-before-
    # hearing window the product spec anticipates; every value is
    # overridable via env without a code change.
    ecourts_sync_start_hour: int = 15  # 3pm IST
    ecourts_sync_end_hour: int = 23  # 11pm IST
    ecourts_sync_interval_minutes: int = 60
    ecourts_sync_lookahead_days: int = 2  # sync matters whose next_hearing_date is within N days

    # Platform-owner allowlist (Enhancement_Roadmap.md §4/§17): comma-
    # separated emails, compared server-side against the already-verified
    # JWT `email` claim in app/auth.py::require_platform_owner. Never
    # trusted from a request header/body — the frontend may use the same
    # address for a nav-visibility hint only, which is not security.
    platform_owner_emails: str = "keshav.karn@gmail.com"

    # LLM providers — failover order per CLAUDE.md Decision 3
    gemini_api_key: str = ""
    groq_api_key: str = ""
    sambanova_api_key: str = ""
    cerebras_api_key: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # "https://vidhidesk.vercel.app" is aspirational -- the actual Vercel
    # project is named "web" (not "vidhidesk"), so its real stable
    # production domain is "https://web-three-phi-94.vercel.app" (confirmed
    # via `vercel domains ls`/`project ls`, 2026-09-08). Both are kept here:
    # the vidhidesk.vercel.app entry costs nothing to keep in case that
    # domain is ever claimed, and removing it isn't this fix's job.
    #
    # Stored as a plain str field (validation_alias keeps it reading from
    # the same CORS_ORIGINS env var), NOT list[str]: pydantic-settings
    # attempts its own JSON-decode of any list[str]-typed field sourced
    # from an env var BEFORE a model_validator/field_validator ever runs,
    # raising a hard SettingsError that crashes the whole app at startup
    # for an ordinary comma-separated value like "http://a,http://b" --
    # even though parsing logic for exactly that shape already existed
    # below. `Annotated[list[str], NoDecode]` is pydantic-settings' own
    # fix for this, but that requires >=2.7; this box runs 2.6.1, where
    # NoDecode does not exist. Verified live: setting CORS_ORIGINS as a
    # comma-separated string in production crash-looped the container with
    # `pydantic_settings.exceptions.SettingsError: error parsing value for
    # field "cors_origins" from source "EnvSettingsSource"`. Parsing into
    # a list now happens explicitly in the cors_origins property below,
    # safely after Settings() has already been constructed.
    cors_origins_raw: str = Field(default="", validation_alias="CORS_ORIGINS")

    _CORS_DEFAULTS = [
        "http://localhost:3000",
        "https://vidhidesk.vercel.app",
        "https://web-three-phi-94.vercel.app",
    ]

    @property
    def cors_origins(self) -> list[str]:
        v_str = (self.cors_origins_raw or "").strip()
        if not v_str:
            return self._CORS_DEFAULTS
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


@lru_cache
def get_settings() -> Settings:
    return Settings()

