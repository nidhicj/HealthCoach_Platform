from unittest.mock import patch

import pytest
from sqlalchemy import select

from src.config import get_settings
from src.db.models import CheckIn, Client
from tests.integration.conftest import _make_user


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


@pytest.mark.asyncio
async def test_scheduled_tasks_one_client_send_failure_does_not_block_or_roll_back_others(
    http_client, hc_user, client_rec, db,
):
    """Regression test for per-client failure isolation.

    Before the fix, `_run_check_in_reminders` committed only once at the end
    of the loop, inside a single try-less `for` block. One client's send
    failure (bad address / Resend rate limit / transient network error)
    would propagate, roll back the *entire* session — wiping out the pending
    CheckIn rows already created for clients processed earlier in the same
    run, even though those clients had already been emailed — and would also
    stop the loop, so clients later in iteration order got neither a row nor
    an email.

    This test creates three eligible clients, makes the send fail for the
    middle one, and asserts: the other two clients each still have exactly
    one pending CheckIn row and were still emailed, the failing client has
    no pending row, and the response reports accurate sent/failed counts.
    """
    client_rec.email = "good1@example.com"
    await db.flush()

    bad_user = await _make_user(db, "client")
    bad_client = Client(
        hc_user_id=hc_user.id,
        full_name="Bad Client",
        user_id=bad_user.id,
        email="bad@example.com",
    )
    db.add(bad_client)

    good_user2 = await _make_user(db, "client")
    good_client2 = Client(
        hc_user_id=hc_user.id,
        full_name="Good Client 2",
        user_id=good_user2.id,
        email="good2@example.com",
    )
    db.add(good_client2)
    await db.flush()
    await db.commit()

    # Capture ids now — the scheduler run below calls db.rollback() for the
    # failing client, which (correctly) expires every ORM object still held
    # in the session's identity map, including these. Reading .id off the
    # ORM objects after that would itself trigger the same implicit-lazy-load
    # failure the fix has to avoid.
    good_client_id_1 = client_rec.id
    good_client_id_2 = good_client2.id
    bad_client_id = bad_client.id

    def _send_side_effect(*, to, client_name, portal_url):
        if to == "bad@example.com":
            raise RuntimeError("simulated Resend failure")

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch(
             "src.api.scheduler.send_check_in_reminder_email",
             side_effect=_send_side_effect,
         ) as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={
                "X-Scheduler-Token": get_settings().scheduler_secret,
                "X-Scheduled-Task": "check_in_reminders",
            },
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reminder_sent_count"] == 2
    assert body["reminder_failed_count"] == 1
    assert mock_email.call_count == 3  # attempted for all three, one raised

    rows = (await db.execute(select(CheckIn))).scalars().all()
    rows_by_client = {row.client_id: row for row in rows}

    assert good_client_id_1 in rows_by_client
    assert good_client_id_2 in rows_by_client
    assert bad_client_id not in rows_by_client
