"""Auth flow integration tests. Per ADR-0005 P2 acceptance criteria."""
import hashlib
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.refresh import issue_refresh_token, revoke_token, rotate_refresh_token
from src.db.models import AuthRefreshToken, User


# ── helpers ───────────────────────────────────────────────────────────────────

async def _make_user(db: AsyncSession) -> User:
    user = User(
        email=f"auth-{uuid.uuid4().hex[:8]}@test.com",
        google_sub=f"g-{uuid.uuid4().hex}",
    )
    db.add(user)
    await db.flush()
    return user


# ── refresh token lifecycle ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token_rotation(db: AsyncSession) -> None:
    """Rotate once → new token works; old token triggers replay detection."""
    user = await _make_user(db)

    raw = await issue_refresh_token(db, user.id)
    new_raw, user_id = await rotate_refresh_token(db, raw)
    assert user_id == user.id
    assert new_raw != raw

    # Old token has successor_id set → replay detection fires
    with pytest.raises(ValueError, match="replay"):
        await rotate_refresh_token(db, raw)


@pytest.mark.asyncio
async def test_refresh_token_replay_revokes_all(db: AsyncSession) -> None:
    """Present old token after rotation → replay detected → all sessions revoked."""
    user = await _make_user(db)

    raw = await issue_refresh_token(db, user.id)
    await rotate_refresh_token(db, raw)  # legitimate rotation

    # Attacker presents the original token again
    with pytest.raises(ValueError, match="replay"):
        await rotate_refresh_token(db, raw)

    # All refresh tokens for user must now be revoked
    active = (await db.execute(
        select(AuthRefreshToken).where(
            AuthRefreshToken.user_id == user.id,
            AuthRefreshToken.revoked_at.is_(None),
        )
    )).scalars().all()
    assert active == []


@pytest.mark.asyncio
async def test_logout_revokes_token(db: AsyncSession) -> None:
    user = await _make_user(db)

    raw = await issue_refresh_token(db, user.id)
    await revoke_token(db, raw)
    await db.flush()

    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token = (await db.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )).scalar_one()
    assert token.revoked_at is not None


@pytest.mark.asyncio
async def test_revoked_token_rejected(db: AsyncSession) -> None:
    """Directly revoked token (no successor) raises 'revoked', not 'replay'."""
    user = await _make_user(db)

    raw = await issue_refresh_token(db, user.id)
    await revoke_token(db, raw)

    with pytest.raises(ValueError, match="revoked"):
        await rotate_refresh_token(db, raw)
