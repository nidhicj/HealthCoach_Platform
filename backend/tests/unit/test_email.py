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


def test_send_lead_test_recommendation_email_calls_resend_with_correct_args():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_test_recommendation_email
        send_lead_test_recommendation_email(
            to="lead@example.com",
            lead_name="Rajesh Kumar",
            hc_name="Dr. Priya Sharma",
            recommended_tests=["CBC", "HbA1c", "Lipid Profile"],
            upload_link="https://parivarthan.app/upload/abc123token",
            expiry_days=14,
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["lead@example.com"]
    assert "Dr. Priya Sharma" in call_kwargs["subject"]
    assert "Rajesh Kumar" in call_kwargs["html"]
    assert "CBC" in call_kwargs["html"]
    assert "HbA1c" in call_kwargs["html"]
    assert "Lipid Profile" in call_kwargs["html"]
    assert "https://parivarthan.app/upload/abc123token" in call_kwargs["html"]


def test_send_lead_test_recommendation_email_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr("src.lib.email._get_api_key", lambda: "")
    from src.lib import email as email_mod
    with pytest.raises(RuntimeError, match="resend_api_key not configured"):
        email_mod.send_lead_test_recommendation_email(
            to="x@x.com",
            lead_name="Test Lead",
            hc_name="Test HC",
            recommended_tests=["CBC"],
            upload_link="https://example.com/upload/token",
            expiry_days=14,
        )


def test_send_lead_test_recommendation_email_escapes_special_chars():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_test_recommendation_email
        send_lead_test_recommendation_email(
            to="c@c.com",
            lead_name="Lead <script>",
            hc_name="HC & Co",
            recommended_tests=["Test <script>alert(1)</script>", "Normal Test"],
            upload_link="https://example.com/upload/token",
            expiry_days=14,
        )
    html = mock_send.call_args[0][0]["html"]
    # Verify no unescaped script tags in the HTML body
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    # Verify names and test names are properly escaped
    assert "Lead &lt;script&gt;" in html
    assert "HC &amp; Co" in html
    # Verify subject line uses raw unescaped hc_name (not HTML entities)
    subject = mock_send.call_args[0][0]["subject"]
    assert "HC & Co" in subject
    assert "&amp;" not in subject


def test_send_lead_brief_ready_email_calls_resend_with_correct_args():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_brief_ready_email
        send_lead_brief_ready_email(
            to="hc@example.com",
            hc_name="Dr. Priya Sharma",
            lead_name="Rajesh Kumar",
            lead_detail_link="https://parivarthan.app/leads/abc-123",
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["hc@example.com"]
    # Subject is short and distinct from the body's opening line.
    assert call_kwargs["subject"] == "Blood report received — Rajesh Kumar"
    # SPEC-0001 Stage 4 step 13's verbatim sentence is the body's opening line.
    assert (
        "Lab reports received from Rajesh Kumar. Pre-consultation brief is ready."
        in call_kwargs["html"]
    )
    assert "Dr. Priya Sharma" in call_kwargs["html"]
    assert "Rajesh Kumar" in call_kwargs["html"]
    assert "https://parivarthan.app/leads/abc-123" in call_kwargs["html"]


def test_send_lead_brief_ready_email_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr("src.lib.email._get_api_key", lambda: "")
    from src.lib import email as email_mod
    with pytest.raises(RuntimeError, match="resend_api_key not configured"):
        email_mod.send_lead_brief_ready_email(
            to="hc@example.com",
            hc_name="Test HC",
            lead_name="Test Lead",
            lead_detail_link="https://example.com/leads/1",
        )


def test_send_lead_brief_ready_email_escapes_special_chars():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_brief_ready_email
        send_lead_brief_ready_email(
            to="hc@example.com",
            hc_name="HC & Co",
            lead_name="Lead <script>alert(1)</script>",
            lead_detail_link="https://example.com/leads/1",
        )
    html = mock_send.call_args[0][0]["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "HC &amp; Co" in html
    # Subject line uses raw unescaped values (it's a mail header, not HTML).
    subject = mock_send.call_args[0][0]["subject"]
    assert "Lead <script>alert(1)</script>" in subject
    assert "&lt;" not in subject


def test_send_lead_brief_ready_email_never_sent_to_lead():
    """The brief is HC-internal per SPEC-0001 §Coach-reviewed gate — this
    email must always go to the HC's address, never the Lead's."""
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_brief_ready_email
        send_lead_brief_ready_email(
            to="hc@example.com",
            hc_name="Dr. Priya Sharma",
            lead_name="Rajesh Kumar",
            lead_detail_link="https://example.com/leads/1",
        )
    assert mock_send.call_args[0][0]["to"] == ["hc@example.com"]


def test_send_lead_brief_failed_email_calls_resend_with_correct_args():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_brief_failed_email
        send_lead_brief_failed_email(
            to="hc@example.com",
            hc_name="Dr. Priya Sharma",
            lead_name="Rajesh Kumar",
            lead_detail_link="https://parivarthan.app/leads/abc-123",
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["hc@example.com"]
    # Subject is short and distinct from the body's opening line.
    assert call_kwargs["subject"] == (
        "Blood report received — brief generation issue (Rajesh Kumar)"
    )
    # SPEC-0001 §Edge cases and failure modes' LLM-failure row, verbatim, is
    # the body's opening line.
    assert (
        "Lab report received, but brief generation failed. "
        "Review files directly from the Lead profile." in call_kwargs["html"]
    )
    assert "Dr. Priya Sharma" in call_kwargs["html"]
    assert "Rajesh Kumar" in call_kwargs["html"]
    assert "https://parivarthan.app/leads/abc-123" in call_kwargs["html"]


def test_send_lead_brief_failed_email_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr("src.lib.email._get_api_key", lambda: "")
    from src.lib import email as email_mod
    with pytest.raises(RuntimeError, match="resend_api_key not configured"):
        email_mod.send_lead_brief_failed_email(
            to="hc@example.com",
            hc_name="Test HC",
            lead_name="Test Lead",
            lead_detail_link="https://example.com/leads/1",
        )


def test_send_lead_brief_failed_email_escapes_special_chars():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_brief_failed_email
        send_lead_brief_failed_email(
            to="hc@example.com",
            hc_name="HC & Co",
            lead_name="Lead <script>alert(1)</script>",
            lead_detail_link="https://example.com/leads/1",
        )
    html = mock_send.call_args[0][0]["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "HC &amp; Co" in html


def test_send_lead_brief_failed_email_never_sent_to_lead():
    """The brief is HC-internal per SPEC-0001 §Coach-reviewed gate — this
    email must always go to the HC's address, never the Lead's."""
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_lead_brief_failed_email
        send_lead_brief_failed_email(
            to="hc@example.com",
            hc_name="Dr. Priya Sharma",
            lead_name="Rajesh Kumar",
            lead_detail_link="https://example.com/leads/1",
        )
    assert mock_send.call_args[0][0]["to"] == ["hc@example.com"]


def test_send_test_recommendation_review_email_calls_resend_with_correct_args():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_test_recommendation_review_email
        send_test_recommendation_review_email(
            to="hc@example.com",
            hc_name="Dr. Priya Sharma",
            lead_name="Rajesh Kumar",
            review_link="https://parivarthan.app/leads/abc-123/test-recommendation",
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["hc@example.com"]
    assert "Rajesh Kumar" in call_kwargs["subject"]
    assert "Dr. Priya Sharma" in call_kwargs["html"]
    assert "Rajesh Kumar" in call_kwargs["html"]
    assert "https://parivarthan.app/leads/abc-123/test-recommendation" in call_kwargs["html"]
    # Terminology discipline (SPEC-0001 D-7): never call this the "brief".
    assert "brief" not in call_kwargs["subject"].lower()
    assert "brief" not in call_kwargs["html"].lower()


def test_send_test_recommendation_review_email_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr("src.lib.email._get_api_key", lambda: "")
    from src.lib import email as email_mod
    with pytest.raises(RuntimeError, match="resend_api_key not configured"):
        email_mod.send_test_recommendation_review_email(
            to="hc@example.com",
            hc_name="Test HC",
            lead_name="Test Lead",
            review_link="https://example.com/leads/1/test-recommendation",
        )


def test_send_test_recommendation_review_email_escapes_special_chars():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_test_recommendation_review_email
        send_test_recommendation_review_email(
            to="hc@example.com",
            hc_name="HC & Co",
            lead_name="Lead <script>alert(1)</script>",
            review_link="https://example.com/leads/1/test-recommendation",
        )
    html = mock_send.call_args[0][0]["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "HC &amp; Co" in html
    # Subject line uses raw unescaped values (it's a mail header, not HTML).
    subject = mock_send.call_args[0][0]["subject"]
    assert "Lead <script>alert(1)</script>" in subject
    assert "&lt;" not in subject


def test_send_test_recommendation_review_email_subject_distinct_from_body_opener():
    """Regression test for the subject/body-duplication bug PHASE-03's Task 4
    shipped and had to fix in its own review round: the subject must be a
    short, distinct string from the body's opening (post-greeting) line, not
    byte-identical to it."""
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_test_recommendation_review_email
        send_test_recommendation_review_email(
            to="hc@example.com",
            hc_name="Dr. Priya Sharma",
            lead_name="Rajesh Kumar",
            review_link="https://example.com/leads/1/test-recommendation",
        )
    call_kwargs = mock_send.call_args[0][0]
    subject = call_kwargs["subject"]
    assert subject == "New Lead ready for review — Rajesh Kumar"
    assert (
        "Rajesh Kumar just completed their health screening questionnaire, "
        "and the AI has drafted a test panel for them. Please review it "
        "before it goes out." in call_kwargs["html"]
    )
    assert subject != (
        "Rajesh Kumar just completed their health screening questionnaire, "
        "and the AI has drafted a test panel for them. Please review it "
        "before it goes out."
    )


def test_send_test_recommendation_review_email_never_sent_to_lead():
    """The draft is HC-internal until the HC's Send action (SPEC-0001 D-5) —
    this email must always go to the HC's address, never the Lead's."""
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_test_recommendation_review_email
        send_test_recommendation_review_email(
            to="hc@example.com",
            hc_name="Dr. Priya Sharma",
            lead_name="Rajesh Kumar",
            review_link="https://example.com/leads/1/test-recommendation",
        )
    assert mock_send.call_args[0][0]["to"] == ["hc@example.com"]


def test_send_finalized_test_recommendation_email_calls_resend_with_correct_args():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_finalized_test_recommendation_email
        send_finalized_test_recommendation_email(
            to="lead@example.com",
            lead_name="Rajesh Kumar",
            hc_name="Dr. Priya Sharma",
            test_list=["CBC", "HbA1c", "Lipid Profile"],
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["lead@example.com"]
    assert "Dr. Priya Sharma" in call_kwargs["subject"]
    assert "Rajesh Kumar" in call_kwargs["html"]
    assert "CBC" in call_kwargs["html"]
    assert "HbA1c" in call_kwargs["html"]
    assert "Lipid Profile" in call_kwargs["html"]
    # Terminology discipline (SPEC-0001 D-7): never call this the "brief".
    assert "brief" not in call_kwargs["subject"].lower()
    assert "brief" not in call_kwargs["html"].lower()


def test_send_finalized_test_recommendation_email_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr("src.lib.email._get_api_key", lambda: "")
    from src.lib import email as email_mod
    with pytest.raises(RuntimeError, match="resend_api_key not configured"):
        email_mod.send_finalized_test_recommendation_email(
            to="lead@example.com",
            lead_name="Test Lead",
            hc_name="Test HC",
            test_list=["CBC"],
        )


def test_send_finalized_test_recommendation_email_escapes_special_chars():
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_finalized_test_recommendation_email
        send_finalized_test_recommendation_email(
            to="c@c.com",
            lead_name="Lead <script>",
            hc_name="HC & Co",
            test_list=["Test <script>alert(1)</script>", "Normal Test"],
        )
    html = mock_send.call_args[0][0]["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Lead &lt;script&gt;" in html
    assert "HC &amp; Co" in html
    # Subject line uses raw unescaped hc_name (not HTML entities).
    subject = mock_send.call_args[0][0]["subject"]
    assert "HC & Co" in subject
    assert "&amp;" not in subject


def test_send_finalized_test_recommendation_email_subject_distinct_from_body_opener():
    """Regression test for the subject/body-duplication bug PHASE-03's Task 4
    shipped and had to fix in its own review round: the subject must be a
    short, distinct string from the body's opening (post-greeting) line, not
    byte-identical to it."""
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_finalized_test_recommendation_email
        send_finalized_test_recommendation_email(
            to="lead@example.com",
            lead_name="Rajesh Kumar",
            hc_name="Dr. Priya Sharma",
            test_list=["CBC"],
        )
    call_kwargs = mock_send.call_args[0][0]
    subject = call_kwargs["subject"]
    assert subject == "Your recommended tests — Dr. Priya Sharma"
    assert (
        "Your health coach, Dr. Priya Sharma, recommends the following "
        "tests before your first consultation:" in call_kwargs["html"]
    )
    assert subject != (
        "Your health coach, Dr. Priya Sharma, recommends the following "
        "tests before your first consultation:"
    )


def test_send_finalized_test_recommendation_email_no_payment_or_scheduling_cta():
    """PHASE-04 Scope: no payment/scheduling infrastructure exists yet
    (ships in PHASE-05) — this email must not include a payment link, a
    scheduling link, or copy implying the Lead can act right now."""
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send), patch("src.lib.email._get_api_key", return_value="test_key_123"):
        from src.lib.email import send_finalized_test_recommendation_email
        send_finalized_test_recommendation_email(
            to="lead@example.com",
            lead_name="Rajesh Kumar",
            hc_name="Dr. Priya Sharma",
            test_list=["CBC", "HbA1c"],
        )
    html = mock_send.call_args[0][0]["html"].lower()
    for forbidden in ("pay", "razorpay", "schedule", "book", "checkout", "click here to"):
        assert forbidden not in html, f"unexpected CTA-like text: {forbidden!r}"
    assert "href=" not in html
