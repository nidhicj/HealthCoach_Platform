"""Scheduler endpoint — authenticated background tasks per build-plan.md §P7."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select, update

from src.api._check_in_lifecycle import get_or_create_pending_check_in
from src.api.deps import DbDep
from src.config import get_settings
from src.db.models import Client
from src.db.models.coaching import HcStyleSnippet
from src.lib.email import send_check_in_reminder_email
from src.telemetry.log import get_logger

router = APIRouter(prefix="/internal", tags=["scheduler"])

RETIREMENT_THRESHOLD_DAYS = 180


# ── pure functions (unit-testable without DB or HTTP) ──────────────────────


def _should_retire(
    last_used_at: datetime | None,
    created_at: datetime,
    retired_at: datetime | None,
    threshold_days: int = RETIREMENT_THRESHOLD_DAYS,
) -> bool:
    """Return True if this snippet should be retired in the current sweep."""
    if retired_at is not None:
        return False  # already retired — idempotent guard
    reference = last_used_at if last_used_at is not None else created_at
    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
    return reference < cutoff


def _check_scheduler_token(provided: str, expected: str) -> None:
    """Raise ValueError if the provided token does not match the expected secret."""
    if not provided or provided != expected:
        raise ValueError("invalid scheduler token")


def _is_saturday_ist(today: date | None = None) -> bool:
    d = today if today is not None else datetime.now(ZoneInfo("Asia/Kolkata")).date()
    return d.weekday() == 5  # Monday=0 ... Saturday=5


async def _run_check_in_reminders(db) -> int:
    clients = (await db.execute(
        select(Client).where(
            Client.journey_stage != "completed",
            Client.user_id.is_not(None),
            Client.email.is_not(None),
        )
    )).scalars().all()

    sent = 0
    for client in clients:
        await get_or_create_pending_check_in(db, client.id, client.hc_user_id)
        send_check_in_reminder_email(
            to=client.email,
            client_name=client.full_name,
            portal_url=f"{get_settings().frontend_url}/me/checkins",
        )
        sent += 1
    await db.commit()
    return sent


# ── schemas ────────────────────────────────────────────────────────────────


class SchedulerResult(BaseModel):
    tasks_run: list[str]
    retired_count: int


# ── endpoint ───────────────────────────────────────────────────────────────


@router.post("/scheduled-tasks", response_model=SchedulerResult)
async def run_scheduled_tasks(request: Request, db: DbDep) -> SchedulerResult:
    try:
        _check_scheduler_token(
            provided=request.headers.get("X-Scheduler-Token", ""),
            expected=get_settings().scheduler_secret,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid scheduler token",
        )

    logger = get_logger(request_id=getattr(request.state, "request_id", "scheduler"))

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETIREMENT_THRESHOLD_DAYS)
    now = datetime.now(timezone.utc)

    stmt = (
        update(HcStyleSnippet)
        .where(
            and_(
                HcStyleSnippet.retired_at.is_(None),
                func.coalesce(HcStyleSnippet.last_used_at, HcStyleSnippet.created_at)
                < cutoff,
            )
        )
        .values(retired_at=now)
        .returning(HcStyleSnippet.id)
    )
    result = await db.execute(stmt)
    await db.commit()
    retired_count = len(result.fetchall())

    logger.info(
        "scheduled_task_run",
        task="snippet_retirement",
        retired_count=retired_count,
        threshold_days=RETIREMENT_THRESHOLD_DAYS,
    )

    tasks_run = ["snippet_retirement"]
    if _is_saturday_ist():
        reminder_count = await _run_check_in_reminders(db)
        tasks_run.append("check_in_reminders")
        logger.info("scheduled_task_run", task="check_in_reminders", reminder_count=reminder_count)

    return SchedulerResult(tasks_run=tasks_run, retired_count=retired_count)
