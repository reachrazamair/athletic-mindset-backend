"""
CONTENT ROUTER — the site's editable text (the CMS data layer).

Public:
  GET  /content/{locale}   → all site text for a language as { key: value }.
                             Missing keys fall back to English so nothing is blank.
                             Cached in memory; refreshed only when content changes.

Admin only:
  GET  /admin/content      → list the English master strings (for the editor).
  PUT  /admin/content      → save English string(s); every other language is
                             auto-translated and stored. Clears the cache.

Bucket two ("content") from the multilingual plan. Interface text (buttons, nav)
is handled separately on the frontend.
"""

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_role
from app.models import ContentEntry, User
from app.schemas import (
    ContentEntryResponse,
    SaveContentRequest,
    SaveContentResponse,
)
from app.translation import translate_batch

router = APIRouter(tags=["content"])

# --- Simple in-memory cache: locale → { key: value } ---
# Content changes rarely (only when Casey saves), so caching avoids a DB hit on
# every page load. The cache is cleared whenever content is saved.
_content_cache: dict[str, dict[str, str]] = {}
_cache_lock = asyncio.Lock()


def _clear_cache() -> None:
    _content_cache.clear()


async def _build_locale_map(db: AsyncSession, locale: str) -> dict[str, str]:
    """
    Build the full text map for a language: English as the base, with the
    language's own values layered on top. So any key not yet translated shows
    the English text instead of being blank.

    If this language is missing some translations (a brand-new language, or new
    English keys added since), we translate just those on the spot, store them,
    and include them. This is why the backend needs no language list of its own —
    it learns a language the first time the site asks for it.
    """
    master = settings.CONTENT_MASTER_LOCALE

    result = await db.execute(
        select(ContentEntry).where(ContentEntry.locale.in_({master, locale}))
    )
    master_map: dict[str, str] = {}
    locale_map: dict[str, str] = {}
    for entry in result.scalars().all():
        if entry.locale == master:
            master_map[entry.key] = entry.value
        elif entry.locale == locale:
            locale_map[entry.key] = entry.value

    if locale == master:
        return master_map

    # Fill in anything this language is missing, on demand.
    missing = [key for key in master_map if key not in locale_map]
    if missing:
        translations = await translate_batch([master_map[k] for k in missing], locale)
        newly_translated = False
        for key, translated in zip(missing, translations):
            if translated is not None:
                locale_map[key] = translated
                await _upsert(db, key, locale, translated)
                newly_translated = True
        if newly_translated:
            await db.commit()

    # English first, then override with the chosen language where it exists.
    return {**master_map, **locale_map}


@router.get("/content/{locale}")
async def get_content(locale: str, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Return all site text for a language (with English fallback). Cached."""
    cached = _content_cache.get(locale)
    if cached is not None:
        return cached

    async with _cache_lock:
        # Re-check inside the lock in case another request just built it.
        cached = _content_cache.get(locale)
        if cached is not None:
            return cached
        data = await _build_locale_map(db, locale)
        _content_cache[locale] = data
        return data


async def _upsert(db: AsyncSession, key: str, locale: str, value: str) -> None:
    """Insert or update one (key, locale) row."""
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


@router.get("/admin/languages", response_model=list[str])
async def list_languages(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Which languages currently exist in the database (for the CMS indicator)."""
    result = await db.execute(select(ContentEntry.locale).distinct())
    return sorted({row[0] for row in result.all()})


@router.get("/admin/content", response_model=list[ContentEntryResponse])
async def list_content(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List the English master strings (what the editor shows Casey)."""
    result = await db.execute(
        select(ContentEntry)
        .where(ContentEntry.locale == settings.CONTENT_MASTER_LOCALE)
        .order_by(ContentEntry.key)
    )
    return [ContentEntryResponse.model_validate(e) for e in result.scalars().all()]


@router.put("/admin/content", response_model=SaveContentResponse)
async def save_content(
    body: SaveContentRequest,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Save English string(s) and auto-translate them into every language that
    already exists in the database.

    English is stored first (the master). Then every other language currently in
    the database is re-translated for these keys and stored. Languages that
    haven't been requested yet get the latest English automatically the first
    time someone views them. If a translation can't be produced, that language
    falls back to English — a save never fails because of translation.
    """
    master = settings.CONTENT_MASTER_LOCALE

    # 1. Store the English master values.
    for item in body.items:
        await _upsert(db, item.key, master, item.value)

    # 2. Figure out which languages already exist (no hard-coded list needed).
    result = await db.execute(
        select(ContentEntry.locale).where(ContentEntry.locale != master).distinct()
    )
    known_locales = [row[0] for row in result.all()]

    # 3. Re-translate these keys for each existing language and store.
    texts = [item.value for item in body.items]
    translated_any = False
    for locale in known_locales:
        results = await translate_batch(texts, locale)
        for item, translated in zip(body.items, results):
            if translated is not None:
                await _upsert(db, item.key, locale, translated)
                translated_any = True

    await db.commit()
    _clear_cache()

    return SaveContentResponse(
        saved=len(body.items),
        locales=[master, *known_locales],
        translated=translated_any,
    )
