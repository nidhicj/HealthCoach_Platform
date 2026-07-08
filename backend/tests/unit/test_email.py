"""Unit tests for the email service module."""
from unittest.mock import MagicMock, patch

import pytest


def test_send_action_items_email_calls_resend_with_correct_args():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_action_items_email
        send_action_items_email(
            to="client@example.com",
            coach_name="Priya Sharma",
            client_name="Sunita Rao",
            session_date="Monday, 30 June 2026",
            action_items=[
                {"description": "Walk 20 minutes daily", "due_date": "2026-07-15"},
                {"description": "Cut sugar after 7pm", "due_date": None},
            ],
            message="Great session this week, keep it up!",
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["client@example.com"]
    assert "Priya Sharma" in call_kwargs["subject"]
    assert "Sunita Rao" in call_kwargs["html"]
    assert "Walk 20 minutes daily" in call_kwargs["html"]
    assert "Cut sugar after 7pm" in call_kwargs["html"]
    assert "Great session this week" in call_kwargs["html"]


def test_send_action_items_email_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr("src.lib.email._get_api_key", lambda: "")
    from src.lib import email as email_mod
    with pytest.raises(RuntimeError, match="resend_api_key not configured"):
        email_mod.send_action_items_email(
            to="x@x.com", coach_name="A", client_name="B",
            session_date="1 Jan", action_items=[], message="hi",
        )


def test_html_template_escapes_special_chars():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_action_items_email
        send_action_items_email(
            to="c@c.com", coach_name="Coach <B>", client_name="Client & Co",
            session_date="30 Jun",
            action_items=[{"description": "Do <script>alert(1)</script>", "due_date": None}],
            message="Notes with <script>alert(1)</script>",
        )
    html = mock_send.call_args[0][0]["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_send_action_items_email_uses_configured_from_address():
    """The 'from' address must come from settings.resend_from_email, not a
    hardcoded literal — sender domain isn't verified with Resend yet, so this
    needs to be swappable (e.g. sandbox sender) without a code change."""
    mock_send = MagicMock()
    with (
        patch("resend.Emails.send", mock_send),
        patch("src.lib.email._get_api_key", return_value="test_key_123"),
        patch("src.lib.email._get_from_email", return_value="sandbox@resend.dev"),
    ):
        from src.lib.email import send_action_items_email
        send_action_items_email(
            to="client@example.com",
            coach_name="Priya Sharma",
            client_name="Sunita Rao",
            session_date="Monday, 30 June 2026",
            action_items=[],
            message="hi",
        )
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["from"] == "sandbox@resend.dev"


def test_subject_uses_raw_unescaped_names_not_html_entities():
    """Subject is a mail header (plain text), not HTML — it must never contain
    HTML entities like &#x27; or &amp; even when coach/client names contain
    characters that get escaped inside the HTML body (e.g. "D'Souza")."""
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_action_items_email
        send_action_items_email(
            to="client@example.com",
            coach_name="D'Souza & Sons",
            client_name="Sunita Rao",
            session_date="Monday, 30 June 2026",
            action_items=[{"description": "Walk 20 minutes daily", "due_date": None}],
            message="Great session!",
        )
    call_kwargs = mock_send.call_args[0][0]
    assert "D'Souza & Sons" in call_kwargs["subject"]
    assert "&#x27;" not in call_kwargs["subject"]
    assert "&amp;" not in call_kwargs["subject"]
