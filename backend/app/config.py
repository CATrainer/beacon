"""Application configuration, loaded from environment variables.

Every external integration is optional. `Settings` exposes typed accessors and
`*_enabled` helpers so call sites can degrade gracefully when a key is absent —
this is what lets Beacon boot and run locally with an empty `.env`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---------------------------------------------------------------
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://beacon:beacon@db:5432/beacon"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "dev-insecure-change-me"
    access_token_expire_minutes: int = 10080  # 7 days
    jwt_algorithm: str = "HS256"

    cors_origins: str = "http://localhost:5173"

    # --- Local dev convenience ---------------------------------------------
    # When APP_ENV=local and both are set, the entrypoint idempotently seeds
    # this login so you can sign in without running a script. Ignored in prod.
    dev_autoseed_email: str = ""
    dev_autoseed_password: str = ""
    dev_autoseed_name: str = "Dev User"

    # --- AI models ----------------------------------------------------------
    anthropic_api_key: str = ""
    model_default: str = "claude-sonnet-4-6"
    model_high: str = "claude-opus-4-8"
    model_cheap: str = "claude-haiku-4-5"
    # Stage 4 (expensive AI) auto-runs only on the top-N by Stage-3 score (§2).
    research_top_n_default: int = 50

    # --- Source adapters ----------------------------------------------------
    cqc_subscription_key: str = ""
    google_places_api_key: str = ""
    companies_house_api_key: str = ""

    # --- GEO engines --------------------------------------------------------
    perplexity_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # --- Email resolver -----------------------------------------------------
    email_resolver_provider: str = ""
    hunter_api_key: str = ""

    # --- Sending ------------------------------------------------------------
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/integrations/gmail/callback"
    sending_identity: str = "caleb.trainer@heuricity.com"

    # --- Booking ------------------------------------------------------------
    cal_link: str = ""
    cal_webhook_secret: str = ""

    # --- Fetching etiquette -------------------------------------------------
    user_agent: str = "HeuricityBeacon/1.0; hello@heuricity.com"
    fetch_max_rps_per_host: float = Field(default=1.0)

    # --- Derived helpers ----------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def anthropic_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def cqc_enabled(self) -> bool:
        return bool(self.cqc_subscription_key)

    @property
    def google_places_enabled(self) -> bool:
        return bool(self.google_places_api_key)

    @property
    def companies_house_enabled(self) -> bool:
        return bool(self.companies_house_api_key)

    @property
    def email_resolver_enabled(self) -> bool:
        return bool(self.email_resolver_provider and self.hunter_api_key)

    @property
    def gmail_enabled(self) -> bool:
        return bool(self.gmail_client_id and self.gmail_client_secret)

    def geo_engines_available(self) -> list[str]:
        engines = []
        if self.perplexity_api_key:
            engines.append("perplexity")
        if self.openai_api_key:
            engines.append("openai")
        if self.gemini_api_key:
            engines.append("gemini")
        return engines


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
