"""HC-facing calendar-data endpoints (PHASE-01e Task 5).

Distinct from the OAuth-flow routes in src/auth/router.py (connect/callback),
which manage the Google OAuth handshake itself. This router exposes read-only
status about an HC's Google Calendar connection for the Settings UI.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models import GoogleCalendarConnection

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


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
