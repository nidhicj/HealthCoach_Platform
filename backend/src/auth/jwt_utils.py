"""ES256 JWT sign/verify. Per ADR-0005 §2 and §3."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt

_ALGORITHM = "ES256"
_ISSUER = "https://api.parivarthan.com"
_AUDIENCE = "parivarthan-api"
_ACCESS_TTL_SECONDS = 15 * 60  # 15 minutes


class AuthError(Exception):
    """Raised on any JWT validation failure."""


@dataclass
class TokenClaims:
    sub: str
    role: str
    hc_id: str | None
    jti: str
    iat: int
    exp: int
    iss: str = field(default=_ISSUER)


def create_access_token(
    *,
    sub: str,
    role: str,
    hc_id: str | None,
    private_key: str,
    ttl_seconds: int = _ACCESS_TTL_SECONDS,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": sub,
        "role": role,
        "hc_id": hc_id,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, private_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, *, public_key: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token, public_key, algorithms=[_ALGORITHM],
            audience=_AUDIENCE, issuer=_ISSUER,
        )
    except ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except JWTError as exc:
        raise AuthError(f"invalid token: {exc}") from exc

    return TokenClaims(
        sub=payload["sub"],
        role=payload["role"],
        hc_id=payload.get("hc_id"),
        jti=payload["jti"],
        iat=payload["iat"],
        exp=payload["exp"],
        iss=payload["iss"],
    )
