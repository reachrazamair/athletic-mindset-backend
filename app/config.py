"""
CONFIG — The single source of truth for all app settings.

How it works:
- In development: reads values from the .env file in the project root
- In production: reads from real environment variables on the server

Why use this instead of reading os.environ directly?
- Validates that required vars exist at startup (fails fast, not mid-request)
- Provides type safety (DEBUG is a bool, not a string)
- One place to see every setting the app needs
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Athletic Mindset API"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/athletic_mindset"

    # --- Auth ---
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    ALGORITHM: str = "HS256"

    # --- CORS ---
    # Which URLs are allowed to call our API (your Next.js frontend)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # --- Frontend ---
    # Base URL of the Next.js app — used to build links inside emails
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Email ---
    # If RESEND_API_KEY is set, emails are sent for real via Resend.
    # If it's empty (local dev), emails are printed to the console instead.
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Athletic Mindset <onboarding@resend.dev>"

    # Tells Pydantic Settings to load from .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create one instance — import this wherever you need settings
settings = Settings()
