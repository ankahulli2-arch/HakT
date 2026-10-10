from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


    app_name: str = "FSP Talent Platform"
    secret_key: str = "change-me-in-production"


    database_url: str = "postgresql+asyncpg://fsp:fsp@localhost:5432/fsp_talent"


    redis_url: str = "redis://localhost:6379/0"


    frontend_url: str = "http://localhost:3000"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14


    grade_change_cooldown_days: int = 90
    cat_target_items: int = 12
    cat_se_threshold: float = 0.30

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
