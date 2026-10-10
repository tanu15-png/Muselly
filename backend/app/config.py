from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    supabase_url: str = ""
    supabase_publishable_key: str = ""
    database_url: str = ""
    app_origin: str = "http://localhost:5173"
    supabase_service_role_key: str = ""
    supabase_secret_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
