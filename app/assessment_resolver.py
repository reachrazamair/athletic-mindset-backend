"""
ASSESSMENT RESOLVER — swaps a question's prompt text for the athlete taking it.

Some questions in the bank read differently depending on the athlete's sport
category and position (e.g. "teammate" vs "training partner or rival"). The
variant text lives entirely in the question's `sport_category_overrides` and
`position_overrides` JSON columns, edited from the admin panel — this module
only holds the *order* in which those variants are picked, never the text
itself. Sport category and position themselves are athlete-entered, as part
of the assessment's own registration step (AthleteProfile.sport_category /
.position) — not an admin-curated lookup.

Resolution order: position override > sport-category override > default prompt.

Each variant is also independently translatable: `resolve_question_variant`
returns which content-entry key suffix applies (e.g. "prompt" or
"position_overrides.Quarterback") alongside the English fallback text, so the
caller can look up a translation for that *specific* variant rather than
always translating the default prompt.
"""

from app.models import AssessmentQuestion, AthleteProfile, SportCategoryEnum


def resolve_question_variant(question: AssessmentQuestion, profile: AthleteProfile | None) -> tuple[str, str]:
    """Return (content_key_suffix, english_text) for the wording variant this athlete should see."""
    if profile and profile.position and question.position_overrides:
        override = question.position_overrides.get(profile.position)
        if override:
            return f"position_overrides.{profile.position}", override

    category = profile.sport_category if profile and profile.sport_category else SportCategoryEnum.individual
    if question.sport_category_overrides:
        override = question.sport_category_overrides.get(category.value)
        if override:
            return f"sport_category_overrides.{category.value}", override

    return "prompt", question.prompt


def resolve_question_text(question: AssessmentQuestion, profile: AthleteProfile | None) -> str:
    """Convenience wrapper for callers that only need the English text (no translation)."""
    return resolve_question_variant(question, profile)[1]
