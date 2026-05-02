"""App settings loaded from environment via pydantic-settings. Per ADR-0001/ADR-0004."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = ""
    test_database_url: str = ""

    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_algorithm: str = "ES256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    google_client_id: str = ""
    google_client_secret: str = ""

    api_base_url: str = "http://localhost:8000"
    openrouter_api_key: str = ""

    sentry_dsn: str = ""
    app_env: str = "dev"
    app_version: str = "0.1.0"

    @field_validator("database_url", "jwt_private_key", "jwt_public_key", mode="before")
    @classmethod
    def _not_empty_in_prod(cls, v: str, info: object) -> str:
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
