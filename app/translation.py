"""
TRANSLATION — auto-translate content from English into other languages.

Used by the content (CMS) system: when Casey saves an English string, we
translate it into every other supported language and store the results.

Provider: DeepL (set DEEPL_API_KEY). Only this module knows about the provider,
so swapping it later touches nothing else.

If no key is configured, `translate` returns None and the caller simply leaves
that language to fall back to English — nothing breaks.
"""

import httpx

from app.config import settings


async def translate(text: str, target_locale: str) -> str | None:
    """
    Translate one English string into `target_locale`.

    Returns the translated text, or None if translation isn't possible (no key
    configured, or the provider errored). The caller decides what to do with a
    None — we never raise, so a translation hiccup can't break a save.
    """
    return (await translate_batch([text], target_locale))[0]


async def translate_batch(texts: list[str], target_locale: str) -> list[str | None]:
    """
    Translate several English strings into `target_locale` in one request.

    Returns a list the same length as `texts`; any position we couldn't
    translate comes back as None.
    """
    if not texts:
        return []

    if not settings.DEEPL_API_KEY:
        # No provider configured — signal "no translation available".
        return [None] * len(texts)

    payload = {
        "text": texts,
        "target_lang": target_locale.upper(),
        "source_lang": settings.CONTENT_MASTER_LOCALE.upper(),
        "preserve_formatting": True,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                settings.DEEPL_API_URL,
                headers={
                    "Authorization": f"DeepL-Auth-Key {settings.DEEPL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            # Log and fall back — a failed translation must never break a save.
            print(f"❌ Translation failed ({response.status_code}) for '{target_locale}': {response.text}")
            return [None] * len(texts)

        result = response.json()
        return [tr["text"] for tr in result["translations"]]
    except Exception as e:  # noqa: BLE001 — never let translation break the request
        print(f"❌ Translation error for '{target_locale}': {e}")
        return [None] * len(texts)
