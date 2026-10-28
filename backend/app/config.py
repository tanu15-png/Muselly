from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    supabase_url: str = ""
    supabase_publishable_key: str = ""
    database_url: str = ""
    app_origin: str = "http://localhost:5173"
    supabase_service_role_key: str = ""
    supabase_secret_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = Field(default="gemini-3.8-flash", pattern=r"^gemini-[a-z0-9.-]+$", max_length=100)
    gemini_image_model: str = Field(default="gemini-nano-banana-2.1", pattern=r"^gemini-[a-z0-9.-]+$")
    qloo_api_key: str = ""
    # Retain the environment setting name for existing deployments.
    myntra_catalog_path: str = str(BACKEND_ROOT / 'data/multi-retailer/catalog-products.json')
    qloo_base_url: str = Field(default="https://api.qloo.com", pattern=r"^https://[a-zA-Z0-9.-]+(?::[0-9]+)?/?$", max_length=200)


@lru_cache
def get_settings() -> Settings:
    return Settings()
