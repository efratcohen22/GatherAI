from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./gatherai.db"
    auth_mode: str = "local"  # local | supabase
    local_jwt_secret: str = "local-development-only-secret-not-for-production"
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    proposal_ttl_hours: int = 24

    @model_validator(mode="after")
    def refuse_local_auth_outside_development(self) -> "Settings":
        if self.auth_mode == "local" and self.app_env not in ("development", "test"):
            raise ValueError("AUTH_MODE=local is only allowed in development or test")
        if self.auth_mode not in ("local", "supabase"):
            raise ValueError("AUTH_MODE must be local or supabase")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def ai_live(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
