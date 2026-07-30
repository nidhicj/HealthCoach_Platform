from unittest.mock import patch

import pytest

from src.config import get_settings


@pytest.mark.asyncio
async def test_scheduled_tasks_creates_reminder_for_eligible_client_on_saturday(
    http_client, client_rec, db,
):
    client_rec.email = "client@example.com"
    await db.flush()
    await db.commit()

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={
                "X-Scheduler-Token": get_settings().scheduler_secret,
                "X-Scheduled-Task": "check_in_reminders",
            },
        )
    assert r.status_code == 200, r.text
    assert "check_in_reminders" in r.json()["tasks_run"]
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_scheduled_tasks_skips_reminder_on_non_saturday(http_client):
    with patch("src.api.scheduler._is_saturday_ist", return_value=False), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
        )
    assert r.status_code == 200
    assert "check_in_reminders" not in r.json()["tasks_run"]
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_tasks_daily_cron_hit_on_saturday_skips_reminders_without_header(
    http_client, client_rec, db,
):
    """Regression test for the dual-cron duplicate-email bug.

    The daily cron (`0 1 * * *`) also fires on Saturdays, so `_is_saturday_ist()`
    alone is not enough to gate the reminder task — it must also require the
    `X-Scheduled-Task: check_in_reminders` header that only the Saturday-specific
    cron entry (`0 4 * * 6`) sends. Without that header, even on a Saturday,
    reminders must NOT run — only snippet_retirement should appear in tasks_run,
    and no email should be sent.
    """
    client_rec.email = "client4@example.com"
    await db.flush()
    await db.commit()

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
            # No X-Scheduled-Task header — simulates the daily-cron hit.
        )
    assert r.status_code == 200, r.text
    assert r.json()["tasks_run"] == ["snippet_retirement"]
    assert "check_in_reminders" not in r.json()["tasks_run"]
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_tasks_saturday_cron_hit_runs_reminders_with_header(
    http_client, client_rec, db,
):
    """Companion to the regression test above: the Saturday-specific cron entry
    sends the X-Scheduled-Task header, so reminders DO run when both the header
    and `_is_saturday_ist()` are true."""
    client_rec.email = "client5@example.com"
    await db.flush()
    await db.commit()

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={
                "X-Scheduler-Token": get_settings().scheduler_secret,
                "X-Scheduled-Task": "check_in_reminders",
            },
        )
    assert r.status_code == 200, r.text
    assert "check_in_reminders" in r.json()["tasks_run"]
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_scheduled_tasks_skips_client_with_no_linked_user(http_client, client_rec, db):
    client_rec.email = "client3@example.com"
    client_rec.user_id = None  # not yet onboarded to the app
    await db.flush()
    await db.commit()

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={
                "X-Scheduler-Token": get_settings().scheduler_secret,
                "X-Scheduled-Task": "check_in_reminders",
            },
        )
    assert r.status_code == 200
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_tasks_still_emails_client_with_existing_pending_request(
    http_client, hc_headers, client_rec, db,
):
    client_rec.email = "client2@example.com"
    await db.flush()
    await db.commit()

    await http_client.post(f"/api/clients/{client_rec.id}/check-ins/request", headers=hc_headers)

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={
                "X-Scheduler-Token": get_settings().scheduler_secret,
                "X-Scheduled-Task": "check_in_reminders",
            },
        )
    assert r.status_code == 200
    # Already has a pending row — still gets emailed (nudge), but no second row created
    mock_email.assert_called_once()
    count_r = await http_client.get(f"/api/clients/{client_rec.id}/check-ins", headers=hc_headers)
    assert len(count_r.json()["items"]) == 1
