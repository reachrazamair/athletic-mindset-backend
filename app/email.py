"""
EMAIL — Sending transactional emails (password reset, verification).

How it works:
- If RESEND_API_KEY is set in .env, emails are sent for real via Resend's API.
- If it's empty (the default for local dev), the email is printed to the
  terminal instead. 

To go live: create a Resend account, verify the domain, and drop the API key
into .env as RESEND_API_KEY. Nothing else changes.
"""

import httpx

from app.config import settings

RESEND_API_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> bool:
    """
    Send one email. Returns True on success.

    Behaviour:
    - If RESEND_API_KEY is set, the email is sent for real via Resend. This is
      the SAME code path in dev and prod — no difference in behaviour.
    - In DEBUG mode we ALSO print the email to the terminal, so during local
      development you can still grab reset/verification links easily even when
      real sending is on.
    - If no API key is set at all, we fall back to console-only (handy before
      Resend is configured).
    """
    # Dev visibility: always show the email in the terminal while DEBUG is on.
    if settings.DEBUG:
        _log_to_console(to, subject, html, sent=bool(settings.RESEND_API_KEY))

    # No key configured → console-only mode.
    if not settings.RESEND_API_KEY:
        if not settings.DEBUG:
            _log_to_console(to, subject, html, sent=False)
        return True

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": settings.EMAIL_FROM,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
        if response.status_code >= 400:
            print(f"❌ Email send failed ({response.status_code}): {response.text}")
            return False
        return True
    except Exception as e:  # noqa: BLE001 — never let email break the request
        print(f"❌ Email send error: {e}")
        return False


def _log_to_console(to: str, subject: str, html: str, sent: bool = False) -> None:
    """Pretty-print the email to the terminal for local development."""
    banner = "📧 EMAIL (sent via Resend — copy shown for dev)" if sent else "📧 EMAIL (dev mode — not actually sent)"
    print("\n" + "=" * 60)
    print(banner)
    print("=" * 60)
    print(f"To:      {to}")
    print(f"Subject: {subject}")
    print("-" * 60)
    print(html)
    print("=" * 60 + "\n")


def render_email(heading: str, body_html: str, button_label: str | None = None, button_url: str | None = None) -> str:
    """
    Wrap content in a simple, on-brand HTML layout (dark theme, blue accent).

    Keeps every transactional email looking consistent. Pass an optional
    button (label + url) for the main call to action.
    """
    button = ""
    if button_label and button_url:
        button = f"""
        <tr>
          <td style="padding: 8px 0 24px;">
            <a href="{button_url}"
               style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                      font-weight:600;font-size:15px;padding:14px 28px;border-radius:12px;">
              {button_label}
            </a>
          </td>
        </tr>
        """

    return f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0f;padding:40px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="max-width:480px;background:#13131a;border:1px solid #23232e;border-radius:20px;padding:36px 32px;">
            <tr>
              <td style="padding-bottom:20px;font-size:13px;letter-spacing:0.25em;
                         text-transform:uppercase;color:#6b7280;font-weight:700;">
                Athletic Mindset
              </td>
            </tr>
            <tr>
              <td style="font-size:22px;font-weight:800;color:#ffffff;padding-bottom:12px;">
                {heading}
              </td>
            </tr>
            <tr>
              <td style="font-size:15px;line-height:1.6;color:#9ca3af;padding-bottom:24px;">
                {body_html}
              </td>
            </tr>
            {button}
            <tr>
              <td style="border-top:1px solid #23232e;padding-top:20px;font-size:12px;color:#6b7280;line-height:1.5;">
                If you didn't request this, you can safely ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
