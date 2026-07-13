"""HC-facing calendar-data endpoints (PHASE-01e Task 5, Task 6, Task 7).

Distinct from the OAuth-flow routes in src/auth/router.py (connect/callback),
which manage the Google OAuth handshake itself. This router exposes read-only
status about an HC's Google Calendar connection for the Settings UI, the
internal `_get_valid_access_token` chokepoint (Task 6) that later tasks
(7, 12, 15) call before making any real Google Calendar API request, and
(Task 7) a read-only proxy for the HC's upcoming Google Calendar events.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.auth.calendar_oauth import CalendarReauthRequired, refresh_calendar_access_token
from src.config import get_settings
from src.db.models import GoogleCalendarConnection
from src.lib.http import make_http_client
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# Refresh proactively if the stored token expires within this window, so a
# borderline-valid token doesn't die mid-request against the real Google API.
_TOKEN_EXPIRY_BUFFER = timedelta(seconds=60)


class CalendarStatusOut(BaseModel):
    connected: bool
    google_account_email: str | None
    connected_at: datetime | None
    needs_reauth: bool


@router.get("/status")
async def get_calendar_status(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> CalendarStatusOut:
    connection = (await db.execute(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()

    if connection is None:
        return CalendarStatusOut(
            connected=False,
            google_account_email=None,
            connected_at=None,
            needs_reauth=False,
        )

    return CalendarStatusOut(
        connected=True,
        google_account_email=connection.google_account_email,
        connected_at=connection.connected_at,
        needs_reauth=connection.revoked_at is not None,
    )


async def _get_valid_access_token(db: AsyncSession, hc_user_id: UUID) -> str:
    """Return a valid Google Calendar access token for hc_user_id.

    Single chokepoint used by every route that calls the real Google Calendar
    API (Tasks 7, 12, 15) — do not duplicate this refresh/revoke logic at
    call sites.

    Raises:
        HTTPException(409, detail="calendar_not_connected"): no
            GoogleCalendarConnection row exists for this HC. Frontend
            branches on this exact string — keep it stable.
        HTTPException(409, detail="calendar_reauth_required"): the row is
            already revoked, or Google rejected the refresh_token (the HC
            must reconnect via the OAuth connect flow). Frontend branches
            on this exact string — keep it stable.

    Known limitation (deliberately deferred, PHASE-01e Task 6 review): no
    row lock or per-hc_user_id dedup on the refresh path. Two concurrent
    requests both seeing an expired token will both call Google's refresh
    endpoint and both commit — the loser's write is simply overwritten, but
    each caller still gets a valid access_token, so this is a duplicate
    network call, not an incorrect result. Not fixed here; revisit if
    real-world concurrency at this chokepoint becomes a cost/quota concern.
    """
    started = time.monotonic()
    logger = get_logger(request_id="")

    def _log(outcome: str) -> None:
        logger.info(
            "google_calendar_api_call",
            operation="get_valid_access_token",
            hc_id=str(hc_user_id),
            outcome=outcome,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    connection = (await db.execute(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.hc_user_id == hc_user_id)
    )).scalar_one_or_none()

    if connection is None:
        _log("calendar_not_connected")
        raise HTTPException(status_code=409, detail="calendar_not_connected")

    if connection.revoked_at is not None:
        _log("calendar_reauth_required")
        raise HTTPException(status_code=409, detail="calendar_reauth_required")

    now = datetime.now(timezone.utc)
    expires_at = connection.access_token_expires_at
    if expires_at.tzinfo is None:
        # Defensive: Postgres TIMESTAMPTZ round-trips as tz-aware via asyncpg,
        # but guard against a naive value ever reaching here.
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at > now + _TOKEN_EXPIRY_BUFFER:
        _log("valid")
        return str(connection.credentials["access_token"])

    settings = get_settings()
    try:
        new_access_token, expires_in = await refresh_calendar_access_token(
            refresh_token=connection.credentials["refresh_token"],
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
    except CalendarReauthRequired:
        connection.revoked_at = now
        await db.commit()
        _log("calendar_reauth_required")
        raise HTTPException(status_code=409, detail="calendar_reauth_required")
    except Exception:
        # Any other failure (Google 5xx, timeout, malformed token response,
        # etc.) must still produce a structured log line — there is no
        # global exception-logging middleware that would catch this
        # otherwise. Re-raise unchanged; this only adds observability.
        _log("error")
        raise

    # Reassign (rather than mutate in place) so SQLAlchemy's change tracking
    # sees a new value on this EncryptedJSON column and re-encrypts on flush.
    connection.credentials = {**connection.credentials, "access_token": new_access_token}
    connection.access_token_expires_at = now + timedelta(seconds=expires_in)
    connection.updated_at = now
    await db.commit()

    _log("refreshed")
    return new_access_token


class CalendarEventOut(BaseModel):
    id: str
    summary: str
    start: str
    end: str
    hangout_link: str | None
    html_link: str
    location: str | None


def _flatten_google_event_time(value: dict[str, Any]) -> str:
    """Flatten Google's start/end shape to a single ISO string.

    A timed event is `{"dateTime": "2026-07-12T09:00:00+05:30", "timeZone":
    "..."}`; an all-day event is `{"date": "2026-07-12"}` (no `dateTime`).
    This endpoint's flat response shape has one `start`/`end` string field,
    so all-day events surface their date-only string rather than a
    synthesized midnight timestamp — the frontend only displays this and
    does not currently need to distinguish timed vs. all-day here.
    """
    return value.get("dateTime") or value.get("date") or ""


def _map_google_calendar_event(item: dict[str, Any]) -> CalendarEventOut:
    return CalendarEventOut(
        id=item["id"],
        summary=item.get("summary", ""),
        start=_flatten_google_event_time(item.get("start", {})),
        end=_flatten_google_event_time(item.get("end", {})),
        hangout_link=item.get("hangoutLink"),
        html_link=item.get("htmlLink", ""),
        location=item.get("location"),
    )


@router.get("/events")
async def list_calendar_events(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    time_min: str,
    time_max: str,
) -> list[CalendarEventOut]:
    """Proxy Google Calendar's events.list for the HC's primary calendar.

    Read-only: does not write anything to our DB beyond whatever
    `_get_valid_access_token` itself persists (token refresh). Event data
    is not cached or stored here.
    """
    access_token = await _get_valid_access_token(db, UUID(hc_id))

    async with make_http_client() as client:
        resp = await client.get(
            _CALENDAR_EVENTS_URL,
            params={
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": time_min,
                "timeMax": time_max,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    return [_map_google_calendar_event(item) for item in data.get("items", [])]
