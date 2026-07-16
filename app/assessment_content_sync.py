"""
ASSESSMENT CONTENT SYNC — keeps ContentEntry (the site's translation table) in
sync with a question's admin-authored text.

Shared by the admin CRUD router (app/routers/admin_assessment.py — every
create/update/delete) and the seed/startup path (app/seed_assessment.py —
so the initial 40 questions are translatable from first boot, and any
question that predates this sync gets backfilled automatically).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AssessmentQuestion, ContentEntry
from app.routers.content import _clear_cache, _upsert
from app.translation import translate_batch


async def sync_question_content(db: AsyncSession, question: AssessmentQuestion) -> None:
    """
    Mirror a question's translatable text (prompt, helper text, option text,
    and any sport-category/position override wording) into ContentEntry as the
    English master, then refresh translations for every language the site
    already has — the same mechanism the CMS content editor uses for the rest
    of the site's copy. A key that no longer applies (an option that was
    replaced, an override that was removed) is cleaned up across all locales.
    """
    master = settings.CONTENT_MASTER_LOCALE
    prefix = f"assessment.questions.{question.id}."

    items: dict[str, str] = {f"{prefix}prompt": question.prompt}
    if question.helper_text:
        items[f"{prefix}helper_text"] = question.helper_text
    for option in question.options:
        items[f"{prefix}options.{option.id}.text"] = option.text
    for category, text in (question.sport_category_overrides or {}).items():
        items[f"{prefix}sport_category_overrides.{category}"] = text
    for position, text in (question.position_overrides or {}).items():
        items[f"{prefix}position_overrides.{position}"] = text

    # Drop previously-synced keys that no longer apply to this question.
    existing = await db.execute(select(ContentEntry).where(ContentEntry.key.like(f"{prefix}%")))
    for entry in existing.scalars().all():
        if entry.key not in items:
            await db.delete(entry)
    await db.flush()

    for key, value in items.items():
        await _upsert(db, key, master, value)

    locales_result = await db.execute(
        select(ContentEntry.locale).where(ContentEntry.locale != master).distinct()
    )
    known_locales = [row[0] for row in locales_result.all()]

    keys = list(items.keys())
    texts = list(items.values())
    for locale in known_locales:
        translated_texts = await translate_batch(texts, locale)
        for key, translated in zip(keys, translated_texts):
            if translated is not None:
                await _upsert(db, key, locale, translated)

    _clear_cache()


async def delete_question_content(db: AsyncSession, question_id: UUID) -> None:
    """Remove every content-entry row (all locales) belonging to a deleted question."""
    result = await db.execute(
        select(ContentEntry).where(ContentEntry.key.like(f"assessment.questions.{question_id}.%"))
    )
    for entry in result.scalars().all():
        await db.delete(entry)
    _clear_cache()
