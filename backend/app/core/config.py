import json
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False
    # Exact origins only. Accepts a JSON list or a comma-separated string.
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = []

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    ALLOW_REGISTRATION: bool = False

    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_ROOT: str = "./uploads"
    FILE_RETENTION_DAYS: int = 90
    MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024

    OCR_ENGINE: str = "stub"
    OCR_MODEL: str = "claude-sonnet-4-5"

    MARK_SCHEMES_DIR: str = "./mark_schemes"

    ANTHROPIC_API_KEY: str | None = None
    LLM_GRADER_MODEL: str = "claude-sonnet-4-5"

    # Ledger amounts; recorded as owed, paid by hand until Lightning payouts exist
    FEEDBACK_REWARD_SATS: int = Field(default=100, gt=0)
    SCHEME_REWARD_SATS: int = Field(default=500, gt=0)

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            value = json.loads(text) if text.startswith("[") else text.split(",")
        if isinstance(value, list):
            value = [str(origin).strip().rstrip("/") for origin in value if str(origin).strip()]
            # Credentials are allowed, so a wildcard would let any site make authenticated calls
            if "*" in value:
                raise ValueError("ALLOWED_ORIGINS must list exact origins; '*' is not allowed")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
