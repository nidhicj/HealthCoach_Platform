"""Google Calendar incremental-consent OAuth 2.0 Authorization Code + PKCE flow.

Sibling module to oauth.py. Separate, additive flow: an already-authenticated HC
connects their Google Calendar (incremental authorization, per Google's guidance at
https://developers.google.com/identity/protocols/oauth2/web-server#incrementalAuth).
Does not modify or share state with the login flow in oauth.py. Per ADR-0005 §1.
"""
import urllib.parse
from dataclasses import dataclass

from src.lib.http import make_http_client

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_CALENDAR_SCOPES = "openid email profile https://www.googleapis.com/auth/calendar.events"


@dataclass
class GoogleCalendarTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


class MissingRefreshTokenError(Exception):
    """Raised when Google's token response omits refresh_token.

    Google only returns a refresh_token when the user is re-prompted for consent
    (access_type=offline + prompt=consent). If this fires, the connect URL likely
    didn't force re-consent, or the HC has too many outstanding refresh tokens for
    this client (Google's per-account grant limit).
    """


class CalendarReauthRequired(Exception):
    """Raised when Google rejects a refresh_token (revoked/expired).

    The HC must go through build_calendar_connect_url again to reconnect.
    """


def build_calendar_connect_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": _CALENDAR_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_calendar_tokens(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> GoogleCalendarTokens:
    async with make_http_client() as client:
        token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        })
        token_resp.raise_for_status()
        data = token_resp.json()

    if "refresh_token" not in data:
        raise MissingRefreshTokenError(
            "Google token response did not include a refresh_token; "
            "the HC may need to be re-prompted for consent."
        )

    return GoogleCalendarTokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"],
        scope=data.get("scope", _CALENDAR_SCOPES),
    )


async def fetch_calendar_account_email(access_token: str) -> str:
    """Look up the Google account email tied to a Calendar access_token.

    `exchange_code_for_calendar_tokens`'s response never includes an email —
    Google's token endpoint doesn't return one. A `GoogleCalendarConnection`
    row needs a human-readable `google_account_email` (shown in Settings, used
    to detect "wrong account connected"), so the Calendar connect flow makes
    its own lightweight userinfo lookup rather than re-deriving it from the
    separate login flow in oauth.py (whose id_token is not obtained here).
    """
    async with make_http_client() as client:
        resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return str(resp.json()["email"])


async def refresh_calendar_access_token(
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> tuple[str, int]:
    async with make_http_client() as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        })

    if resp.status_code == 400:
        body = resp.json()
        if body.get("error") == "invalid_grant":
            raise CalendarReauthRequired(
                "Google rejected the refresh_token; the HC must reconnect their calendar."
            )

    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["expires_in"]
