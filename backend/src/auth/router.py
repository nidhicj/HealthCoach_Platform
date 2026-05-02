"""Auth endpoints per ADR-0005 §11."""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Client, ClientInviteToken, User
from src.db.session import get_db
from src.auth.jwt_utils import create_access_token
from src.auth.oauth import build_authorization_url, exchange_code_for_userinfo, generate_pkce_pair
from src.auth.refresh import issue_refresh_token, revoke_token, rotate_refresh_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory PKCE state store (Workers KV preferred in prod — acceptable for MVP)
_state_store: dict[str, dict] = {}

_COOKIE_NAME = "refresh_token"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.app_env != "dev",
        samesite="lax",
        path="/api/auth",
        max_age=30 * 24 * 3600,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/api/auth")


@router.get("/google/start")
async def google_start() -> dict:
    settings = get_settings()
    state = str(uuid.uuid4())
    verifier, challenge = generate_pkce_pair()
    _state_store[state] = {"verifier": verifier}
    redirect_uri = f"{settings.api_base_url}/api/auth/google/callback"
    auth_url = build_authorization_url(
        client_id=settings.google_client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=challenge,
    )
    return {"auth_url": auth_url}


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    settings = get_settings()
    stored = _state_store.pop(state, None)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state"
        )

    redirect_uri = f"{settings.api_base_url}/api/auth/google/callback"
    user_info = await exchange_code_for_userinfo(
        code=code,
        code_verifier=stored["verifier"],
        redirect_uri=redirect_uri,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    result = await db.execute(select(User).where(User.google_sub == user_info.sub))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=user_info.email,
            google_sub=user_info.sub,
            display_name=user_info.name,
            photo_url=user_info.picture,
        )
        db.add(user)
        await db.flush()

    access_token = create_access_token(
        sub=str(user.id), role="hc", hc_id=str(user.id),
        private_key=settings.jwt_private_key,
    )
    raw_refresh = await issue_refresh_token(
        db, user.id,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


@router.get("/client/start")
async def client_start(
    invite: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Verify invite token and return Google OAuth URL for client login."""
    await _verify_invite(db, invite)

    settings = get_settings()
    state = str(uuid.uuid4())
    verifier, challenge = generate_pkce_pair()
    _state_store[state] = {
        "verifier": verifier,
        "invite_token_hash": hashlib.sha256(invite.encode()).hexdigest(),
    }
    redirect_uri = f"{settings.api_base_url}/api/auth/client/callback"
    auth_url = build_authorization_url(
        client_id=settings.google_client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=challenge,
    )
    return {"auth_url": auth_url}


@router.get("/client/callback")
async def client_callback(
    code: str,
    state: str,
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange Google code, link client record, and issue a client-role JWT."""
    settings = get_settings()
    stored = _state_store.pop(state, None)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")

    redirect_uri = f"{settings.api_base_url}/api/auth/client/callback"
    user_info = await exchange_code_for_userinfo(
        code=code,
        code_verifier=stored["verifier"],
        redirect_uri=redirect_uri,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    # Re-verify invite (may have expired or been used since start)
    invite = (await db.execute(
        select(ClientInviteToken).where(ClientInviteToken.token_hash == stored["invite_token_hash"])
    )).scalar_one_or_none()
    if invite is None or invite.used_at is not None or invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token has expired or already been used")

    client = (await db.execute(
        select(Client).where(Client.id == invite.client_id)
    )).scalar_one()

    user = (await db.execute(select(User).where(User.google_sub == user_info.sub))).scalar_one_or_none()
    if user is None:
        user = User(
            email=user_info.email,
            google_sub=user_info.sub,
            display_name=user_info.name,
            photo_url=user_info.picture,
            role="client",
        )
        db.add(user)
        await db.flush()

    client.user_id = user.id
    invite.used_at = datetime.now(timezone.utc)
    await db.flush()

    access_token = create_access_token(
        sub=str(user.id),
        role="client",
        hc_id=str(client.hc_user_id),
        private_key=settings.jwt_private_key,
    )
    raw_refresh = await issue_refresh_token(
        db, user.id,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/refresh")
async def refresh_token_endpoint(
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
) -> TokenResponse:
    settings = get_settings()
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token"
        )
    try:
        new_raw, user_id = await rotate_refresh_token(
            db, refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    except ValueError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    if user.role == "client":
        client_rec = (await db.execute(
            select(Client).where(Client.user_id == user.id)
        )).scalar_one_or_none()
        hc_id = str(client_rec.hc_user_id) if client_rec else str(user.id)
    else:
        hc_id = str(user.id)

    await db.commit()

    access_token = create_access_token(
        sub=str(user.id), role=user.role, hc_id=hc_id,
        private_key=settings.jwt_private_key,
    )
    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
) -> dict:
    if refresh_token:
        await revoke_token(db, refresh_token)
        await db.commit()
    _clear_refresh_cookie(response)
    return {"status": "logged_out"}


# ── helpers ─────────────────────────────────────────────────────────────────────


async def _verify_invite(db: AsyncSession, raw_token: str) -> ClientInviteToken:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    invite = (await db.execute(
        select(ClientInviteToken).where(ClientInviteToken.token_hash == token_hash)
    )).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite token")
    if invite.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token already used")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token expired")
    return invite
