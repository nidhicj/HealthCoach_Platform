"""Refresh token lifecycle: issue, rotate, revoke. Per ADR-0005 §5."""
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models import AuthRefreshToken

_REFRESH_TTL_DAYS = 30


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_raw_token() -> str:
    return os.urandom(32).hex()


async def issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_agent: str | None = None,
    ip: str | None = None,
) -> str:
    raw = _generate_raw_token()
    token = AuthRefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=_REFRESH_TTL_DAYS),
        user_agent=user_agent,
        ip_at_issue=ip,
    )
    db.add(token)
    await db.flush()
    return raw


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, uuid.UUID]:
    """Return (new_raw_token, user_id). Raises ValueError on invalid/expired/revoked.
    Replay detected (token already has successor) → revoke ALL sessions for user."""
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise ValueError("refresh token not found")

    now = datetime.now(timezone.utc)

    if token.expires_at.replace(tzinfo=timezone.utc) < now:
        raise ValueError("refresh token expired")

    if token.successor_id is not None:
        await _revoke_all_for_user(db, token.user_id)
        raise ValueError("refresh token replay detected — all sessions revoked")

    if token.revoked_at is not None:
        raise ValueError("refresh token revoked")

    new_raw = _generate_raw_token()
    new_token = AuthRefreshToken(
        user_id=token.user_id,
        token_hash=_hash_token(new_raw),
        expires_at=now + timedelta(days=_REFRESH_TTL_DAYS),
        user_agent=user_agent,
        ip_at_issue=ip,
    )
    db.add(new_token)
    await db.flush()

    token.successor_id = new_token.id
    token.revoked_at = now
    await db.flush()

    return new_raw, token.user_id


async def revoke_token(db: AsyncSession, raw_token: str) -> None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token and token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        await db.flush()


async def _revoke_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AuthRefreshToken)
        .where(
            AuthRefreshToken.user_id == user_id,
            AuthRefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.flush()
