from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TEST_JWT_SECRET = "test-only-secret-used-by-the-automated-test-suite"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "production"  # set APP_ENV=development locally (scripts/setup.ps1 writes .env)
    database_url: str = "sqlite:///./gatherai.db"
    auth_mode: str = "local"  # local | supabase
    local_jwt_secret: str = ""
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    proposal_ttl_hours: int = 24
    # Live model calls allowed per organization in a rolling 24 hours. 0 disables live AI.
    ai_daily_request_limit: int = 300

    @model_validator(mode="after")
    def refuse_local_auth_outside_development(self) -> "Settings":
        if self.auth_mode == "local" and self.app_env not in ("development", "test"):
            raise ValueError("AUTH_MODE=local is only allowed in development or test")
        if self.auth_mode not in ("local", "supabase"):
            raise ValueError("AUTH_MODE must be local or supabase")
        if self.auth_mode == "local":
            if not self.local_jwt_secret and self.app_env == "test":
                self.local_jwt_secret = TEST_JWT_SECRET
            if len(self.local_jwt_secret) < 32:
                raise ValueError("LOCAL_JWT_SECRET must be at least 32 characters (run scripts/setup.ps1 to generate one)")
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
