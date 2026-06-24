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
    # This URL tells SQLAlchemy: use asyncpg driver, connect to postgres on localhost
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/athletic_mindset"

    # --- CORS ---
    # Which URLs are allowed to call our API (your Next.js frontend)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Tells Pydantic Settings to load from .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create one instance — import this wherever you need settings
settings = Settings()
