from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = "sk-placeholder"

    # Data sources
    apollo_api_key: str = "placeholder"
    hunter_api_key: str = "placeholder"
    google_maps_api_key: str = "placeholder"

    # Database
    supabase_url: str = "https://placeholder.supabase.co"
    supabase_key: str = "placeholder"

    # Gmail
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # App limits
    max_leads_per_run: int = 200
    daily_email_limit: int = 50
    backend_url: str = "http://localhost:8000"

    # Security — CHANGE THIS IN PRODUCTION
    api_secret_key: str = "change-this-secret-key-in-production-use-long-random-string"
    n8n_webhook_secret: str = "change-this-n8n-webhook-secret"

    # Optional integrations
    sendgrid_api_key: Optional[str] = None
    phantombuster_api_key: Optional[str] = None
    apify_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
