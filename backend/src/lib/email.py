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


def send_lead_test_recommendation_email(
    *,
    to: str,
    lead_name: str,
    hc_name: str,
    recommended_tests: list[str],
    upload_link: str,
    expiry_days: int = 14,
) -> None:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_lead = html.escape(lead_name)
    safe_hc = html.escape(hc_name)

    # Build bulleted list of tests, escaping each one
    tests_html = "".join(
        f"<li>{html.escape(test)}</li>"
        for test in recommended_tests
    )

    # Subject is a plain-text mail header, not HTML — must use raw values,
    # not the HTML-escaped ones (which would leak entities like &#x27; into
    # the recipient's inbox subject line, e.g. for names like "D'Souza").
    subject = f"Your health screening next steps — {hc_name}"
    body_html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{html.escape(subject)}</title>
    </head>
    <body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #2C2C1E; background: #F7F4EE;">
        <div style="background: #5C6652; padding: 20px 24px; border-radius: 8px 8px 0 0;">
        <h1 style="color: #F7F4EE; font-size: 20px; margin: 0;">Tapas</h1>
        </div>
        <div style="background: #ffffff; padding: 28px 24px; border-radius: 0 0 8px 8px; border: 1px solid #E8EDE5;">
        <p style="font-size: 15px; margin-top: 0;">Hi {safe_lead},</p>
        <p style="font-size: 15px;">Thank you for completing your health screening questionnaire with {safe_hc}. Based on your responses, we recommend the following
    blood tests to give your coach a complete clinical picture before your first session:</p>
        <ul style="font-size: 14px; line-height: 1.8;">{tests_html}</ul>
        <p style="font-size: 15px;">Once you've completed your tests, please upload your lab reports using the secure link below. Your results will be kept confidential 
    and used only for your consultation preparation.</p>
        <div style="background: #F7F4EE; padding: 16px; border-radius: 4px; margin: 20px 0; text-align: center;">
            <p style="font-size: 14px; margin: 0 0 12px 0; color: #2C2C1E;">
            <a href="{upload_link}" style="color: #5C6652; text-decoration: none; font-weight: bold;">Upload Your Lab Reports</a>
            </p>
            <p style="font-size: 12px; color: #888; margin: 0;">Please upload within {expiry_days} days</p>
        </div>
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

def send_lead_brief_ready_email(
    *,
    to: str,
    hc_name: str,
    lead_name: str,
    lead_detail_link: str,
) -> None:
    """Notify the HC that a Lead's blood report was received and the
    pre-consultation brief has been generated. Sent to the HC (`to` is the
    HC's `users.email`), never to the Lead — the brief is HC-internal per
    SPEC-0001 §Coach-reviewed gate. SPEC-0001 Stage 4 step 13.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_hc = html.escape(hc_name)
    safe_lead = html.escape(lead_name)

    # Subject is a plain-text mail header, not HTML — must use raw values,
    # not the HTML-escaped ones (which would leak entities like &#x27; into
    # the recipient's inbox subject line, e.g. for names like "D'Souza").
    # Wording is SPEC-0001 Stage 4 step 13, verbatim with [Lead Name] filled in.
    subject = f"Lab reports received from {lead_name}. Pre-consultation brief is ready."
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
    <p style="font-size: 15px; margin-top: 0;">Hi {safe_hc},</p>
    <p style="font-size: 15px;">Lab reports received from {safe_lead}. Pre-consultation brief is ready.</p>
    <p style="margin: 24px 0;">
      <a href="{lead_detail_link}" style="background: #5C6652; color: #F7F4EE; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">View pre-consultation brief</a>
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


def send_lead_brief_failed_email(
    *,
    to: str,
    hc_name: str,
    lead_name: str,
    lead_detail_link: str,
) -> None:
    """Notify the HC that a Lead's blood report was received but automatic
    brief generation failed. Sent to the HC (`to` is the HC's `users.email`),
    never to the Lead. Wording is SPEC-0001 §Edge cases and failure modes,
    "LLM brief generation fails" row.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_hc = html.escape(hc_name)
    safe_lead = html.escape(lead_name)

    # Subject is a plain-text mail header, not HTML — must use raw values,
    # not the HTML-escaped ones (which would leak entities like &#x27; into
    # the recipient's inbox subject line, e.g. for names like "D'Souza").
    # Wording is SPEC-0001 §Edge cases and failure modes, LLM-failure row, verbatim.
    subject = "Lab report received, but brief generation failed. Review files directly from the Lead profile."
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
    <p style="font-size: 15px; margin-top: 0;">Hi {safe_hc},</p>
    <p style="font-size: 15px;">Lab report received, but brief generation failed. Review files directly from the Lead profile.</p>
    <p style="font-size: 13px; color: #888;">Lead: {safe_lead}</p>
    <p style="margin: 24px 0;">
      <a href="{lead_detail_link}" style="background: #5C6652; color: #F7F4EE; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">View Lead profile</a>
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
            <a href="{portal_url}" style="background: #5C6652; color: #F7F4EE; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">Fill in
    check-in</a>
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