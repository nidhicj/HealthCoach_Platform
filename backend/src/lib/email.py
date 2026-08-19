"""Transactional email via Resend. All outbound emails go through here."""
import html

import resend

from src.config import get_settings


def _get_api_key() -> str:
    return get_settings().resend_api_key


def _get_from_email() -> str:
    return get_settings().resend_from_email


def send_action_items_email(
    *,
    to: str,
    coach_name: str,
    client_name: str,
    session_date: str,
    action_items: list[dict],
    message: str,
) -> None:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_client = html.escape(client_name)
    safe_message = html.escape(message).replace("\n", "<br>")

    items_html = "".join(
        f'<li>{html.escape(item["description"])}'
        + (f' <span style="color:#888;">(due {html.escape(item["due_date"])})</span>' if item.get("due_date") else "")
        + "</li>"
        for item in action_items
    )

    # Subject is a plain-text mail header, not HTML — must use raw values,
    # not the HTML-escaped ones (which would leak entities like &#x27; into
    # the recipient's inbox subject line, e.g. for names like "D'Souza").
    subject = f"Your action items from {coach_name} — {session_date}"
    safe_subject = html.escape(subject)

    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_subject}</title>
</head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #2C2C1E; background: #F7F4EE;">
  <div style="background: #5C6652; padding: 20px 24px; border-radius: 8px 8px 0 0;">
    <h1 style="color: #F7F4EE; font-size: 20px; margin: 0;">Tapas</h1>
  </div>
  <div style="background: #ffffff; padding: 28px 24px; border-radius: 0 0 8px 8px; border: 1px solid #E8EDE5;">
    <p style="font-size: 15px; margin-top: 0;">Hi {safe_client},</p>
    <p style="font-size: 15px; white-space: pre-line;">{safe_message}</p>
    <hr style="border: none; border-top: 1px solid #E8EDE5; margin: 20px 0;">
    <p style="font-size: 13px; font-weight: bold; text-transform: uppercase; color: #888;">This week's action items</p>
    <ul style="font-size: 14px; line-height: 1.8;">{items_html}</ul>
    <hr style="border: none; border-top: 1px solid #E8EDE5; margin: 20px 0;">
    <p style="font-size: 12px; color: #888;">Sent via Tapas · your health coaching platform</p>
  </div>
</body>
</html>"""

    resend.Emails.send({
        "from": _get_from_email(),
        "to": [to],
        "subject": subject,
        "html": body_html,
    })


def send_message_notification_email(*, to: str, client_name: str, coach_name: str, preview: str, portal_url: str) -> None:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_client = html.escape(client_name)
    safe_preview = html.escape(preview[:200])
    subject = f"Your coach replied — {coach_name}"
    safe_subject = html.escape(subject)

    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_subject}</title>
</head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #2C2C1E; background: #F7F4EE;">
  <div style="background: #5C6652; padding: 20px 24px; border-radius: 8px 8px 0 0;">
    <h1 style="color: #F7F4EE; font-size: 20px; margin: 0;">Tapas</h1>
  </div>
  <div style="background: #ffffff; padding: 28px 24px; border-radius: 0 0 8px 8px; border: 1px solid #E8EDE5;">
    <p style="font-size: 15px; margin-top: 0;">Hi {safe_client},</p>
    <p style="font-size: 15px; white-space: pre-line;">{safe_preview}</p>
    <p style="margin: 24px 0;">
      <a href="{portal_url}" style="background: #5C6652; color: #F7F4EE; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">Open chat</a>
    </p>
    <hr style="border: none; border-top: 1px solid #E8EDE5; margin: 20px 0;">
    <p style="font-size: 12px; color: #888;">Sent via Tapas · your health coaching platform</p>
  </div>
</body>
</html>"""

    resend.Emails.send({
        "from": _get_from_email(),
        "to": [to],
        "subject": subject,
        "html": body_html,
    })


def send_check_in_reminder_email(*, to: str, client_name: str, portal_url: str) -> None:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_client = html.escape(client_name)
    subject = "Your check-in"
    safe_subject = html.escape(subject)

    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_subject}</title>
</head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #2C2C1E; background: #F7F4EE;">
  <div style="background: #5C6652; padding: 20px 24px; border-radius: 8px 8px 0 0;">
    <h1 style="color: #F7F4EE; font-size: 20px; margin: 0;">Tapas</h1>
  </div>
  <div style="background: #ffffff; padding: 28px 24px; border-radius: 0 0 8px 8px; border: 1px solid #E8EDE5;">
    <p style="font-size: 15px; margin-top: 0;">Hi {safe_client},</p>
    <p style="font-size: 15px;">Time for a check-in — pick any 3 metrics and rate how your week went.</p>
    <p style="margin: 24px 0;">
      <a href="{portal_url}" style="background: #5C6652; color: #F7F4EE; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">Fill in check-in</a>
    </p>
    <hr style="border: none; border-top: 1px solid #E8EDE5; margin: 20px 0;">
    <p style="font-size: 12px; color: #888;">Sent via Tapas · your health coaching platform</p>
  </div>
</body>
</html>"""

    resend.Emails.send({
        "from": _get_from_email(),
        "to": [to],
        "subject": subject,
        "html": body_html,
    })
