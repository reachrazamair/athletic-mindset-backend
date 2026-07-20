"""
ASSESSMENT CONTENT SYNC — builds the translatable-text mapping for one
question and hands it to the shared sync mechanics in app/routers/content.py
(sync_prefixed_content/delete_prefixed_content).

Shared by the admin CRUD router (app/routers/admin_assessment.py — every
create/update/delete) and the seed/startup path (app/seed_assessment.py —
so the initial questions are translatable from first boot, and any question
that predates this sync gets backfilled automatically).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssessmentQuestion
from app.routers.content import delete_prefixed_content, sync_prefixed_content


async def sync_question_content(db: AsyncSession, question: AssessmentQuestion) -> None:
    """Mirror a question's prompt, helper text, and option text into ContentEntry."""
    items: dict[str, str] = {"prompt": question.prompt}
    if question.helper_text:
        items["helper_text"] = question.helper_text
    for option in question.options:
        items[f"options.{option.id}.text"] = option.text

    await sync_prefixed_content(db, f"assessment.questions.{question.id}.", items)


async def delete_question_content(db: AsyncSession, question_id: UUID) -> None:
    await delete_prefixed_content(db, f"assessment.questions.{question_id}.")
