"""FastAPI dependencies: require_role(), current_tenant(). Per ADR-0005 §7."""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import get_settings
from src.auth.jwt_utils import AuthError, TokenClaims, decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    claims: TokenClaims


def _get_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenClaims:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )
    try:
        claims = decode_access_token(
            credentials.credentials, public_key=get_settings().jwt_public_key
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return claims


def require_role(*roles: str):  # type: ignore[no-untyped-def]
    """FastAPI dependency factory. Usage: Depends(require_role('hc'))"""
    def _check(claims: Annotated[TokenClaims, Depends(_get_claims)]) -> TokenClaims:
        if claims.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
            )
        return claims
    return _check


def current_tenant(
    claims: Annotated[TokenClaims, Depends(_get_claims)],
) -> str:
    """Return hc_id from the JWT. All domain queries must filter by this."""
    if claims.hc_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant context in token",
        )
    return claims.hc_id
