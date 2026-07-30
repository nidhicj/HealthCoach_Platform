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
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
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
async def test_scheduled_tasks_skips_client_with_no_linked_user(http_client, client_rec, db):
    client_rec.email = "client3@example.com"
    client_rec.user_id = None  # not yet onboarded to the app
    await db.flush()
    await db.commit()

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
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
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
        )
    assert r.status_code == 200
    # Already has a pending row — still gets emailed (nudge), but no second row created
    mock_email.assert_called_once()
    count_r = await http_client.get(f"/api/clients/{client_rec.id}/check-ins", headers=hc_headers)
    assert len(count_r.json()["items"]) == 1
