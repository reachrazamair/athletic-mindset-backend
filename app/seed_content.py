"""
SEED CONTENT — load the initial site text into the database.

Run once (and re-run safely) to populate the content table with the English
master strings and their auto-translated versions.

    uv run python -m app.seed_content

Idempotent: existing keys are updated, not duplicated. As we move more pages
into the content system, add their English strings to CONTENT below.
"""

import asyncio

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import ContentEntry

# English master strings, keyed the same way the frontend reads them.
# (Batch 1: home page hero.)
CONTENT: dict[str, str] = {
    "home.hero.badge": "Trusted by 5,000+ athletes nationwide",
    "home.hero.titleTop": "We Measure Your",
    "home.hero.titleBottom": "Athletic Mindset",
    "home.hero.subtitle": (
        "The only psychologist-engineered assessment that measures 22 dimensions "
        "of your mental game in 15 minutes. So you can train it."
    ),
    "home.hero.cta": "Take Free Assessment",
    "home.hero.note": "No credit card required · 15 min · Instant results",
    "home.hero.pllPartner": "Official PLL Academy Partner",
    "home.hero.trust1": "Engineered by Psychologists",
    "home.hero.trust2": "Science-Backed",
    "home.hero.trust3": "Used by Universities & Clubs",
    "home.hero.scroll": "Scroll to explore",
}


async def _upsert(db, key: str, locale: str, value: str) -> None:
    result = await db.execute(
        select(ContentEntry).where(
            ContentEntry.key == key, ContentEntry.locale == locale
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        db.add(ContentEntry(key=key, locale=locale, value=value))
    else:
        entry.value = value


async def main() -> None:
    master = settings.CONTENT_MASTER_LOCALE

    async with AsyncSessionLocal() as db:
        # Store only the English master. Other languages are translated
        # automatically the first time the site requests them.
        for key, value in CONTENT.items():
            await _upsert(db, key, master, value)
        await db.commit()
        print(f"✓ stored {len(CONTENT)} English string(s)")
    print("Done seeding content. Other languages fill in on first view.")


if __name__ == "__main__":
    asyncio.run(main())
