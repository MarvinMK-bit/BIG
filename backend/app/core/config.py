from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = []

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_ROOT: str = "./uploads"
    FILE_RETENTION_DAYS: int = 90
    MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
