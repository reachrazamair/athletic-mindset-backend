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
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # login session length — 7 days
    RESET_TOKEN_EXPIRE_MINUTES: int = 30  # password-reset link lifetime
    VERIFY_TOKEN_EXPIRE_MINUTES: int = 1440  # email-verification link lifetime — 24h

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

    # --- Content translation (CMS) ---
    # English is the master that everything is translated from. The backend does
    # NOT keep its own list of languages: it translates a language on first
    # request and updates every language that already exists when English is
    # saved. So the frontend languages list stays the single source of truth and
    # this never needs manual syncing.
    CONTENT_MASTER_LOCALE: str = "en"
    # DeepL is used to auto-translate content when English is saved.
    DEEPL_API_KEY: str = ""
    DEEPL_API_URL: str = "https://api-free.deepl.com/v2/translate"

    # --- Billing (Stripe) ---
    # The Elite plan is gated behind an active Stripe subscription (Free is
    # granted directly, no Stripe involved — see POST /billing/subscribe-free).
    # From the Stripe dashboard: the secret key from Developers > API keys,
    # and the webhook secret from Developers > Webhooks once you've added an
    # endpoint pointing at {this API}/billing/webhook. Empty in dev = billing
    # routes will fail loudly instead of silently accepting fake payments.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    # One-time bootstrap only: the two recurring Prices you create on the
    # Elite product when first setting up Stripe. Used once, at startup, to
    # backfill the "elite" PricingPlan row with its real Stripe product/price
    # IDs — after that, checkout reads the price straight from that row, and
    # admins change the price via PATCH /admin/pricing/plans/{id}/price
    # instead of editing these. Safe to leave set; safe to clear afterward.
    STRIPE_PRICE_ID_MONTHLY: str = ""
    STRIPE_PRICE_ID_YEARLY: str = ""

    # Tells Pydantic Settings to load from .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create one instance — import this wherever you need settings
settings = Settings()
