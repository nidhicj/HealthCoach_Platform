"""Unit tests for calendar_oauth.py — incremental-consent Google Calendar OAuth helpers.

HTTP calls are mocked via httpx.MockTransport (no real network, no respx dependency),
mirroring this codebase's existing httpx-based DIY philosophy (ADR-0005 §1) and the
make_http_client() factory used by src/lib/http.py.
"""
import urllib.parse

import httpx
import pytest

from src.auth.calendar_oauth import (
    _CALENDAR_SCOPES,
    CalendarReauthRequired,
    GoogleCalendarTokens,
    MissingRefreshTokenError,
    build_calendar_connect_url,
    exchange_code_for_calendar_tokens,
    refresh_calendar_access_token,
)


def _query(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    return {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}


def test_build_calendar_connect_url_includes_scope_and_consent_params() -> None:
    url = build_calendar_connect_url(
        client_id="client-123",
        redirect_uri="https://app.example.com/callback",
        state="state-abc",
        code_challenge="challenge-xyz",
    )
    params = _query(url)
    assert params["scope"] == _CALENDAR_SCOPES
    assert params["prompt"] == "consent"
    assert params["include_granted_scopes"] == "true"


@pytest.mark.asyncio
async def test_exchange_code_for_calendar_tokens_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "at-123",
                "refresh_token": "rt-456",
                "expires_in": 3599,
                "scope": _CALENDAR_SCOPES,
            },
        )

    monkeypatch.setattr(
        "src.auth.calendar_oauth.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    tokens = await exchange_code_for_calendar_tokens(
        code="auth-code",
        code_verifier="verifier",
        redirect_uri="https://app.example.com/callback",
        client_id="client-123",
        client_secret="secret",
    )

    assert tokens == GoogleCalendarTokens(
        access_token="at-123",
        refresh_token="rt-456",
        expires_in=3599,
        scope=_CALENDAR_SCOPES,
    )


@pytest.mark.asyncio
async def test_exchange_code_for_calendar_tokens_missing_refresh_token_raises_specific_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "at-123",
                "expires_in": 3599,
                "scope": _CALENDAR_SCOPES,
            },
        )

    monkeypatch.setattr(
        "src.auth.calendar_oauth.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(MissingRefreshTokenError):
        await exchange_code_for_calendar_tokens(
            code="auth-code",
            code_verifier="verifier",
            redirect_uri="https://app.example.com/callback",
            client_id="client-123",
            client_secret="secret",
        )


@pytest.mark.asyncio
async def test_refresh_calendar_access_token_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": "at-new-789", "expires_in": 3599},
        )

    monkeypatch.setattr(
        "src.auth.calendar_oauth.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    access_token, expires_in = await refresh_calendar_access_token(
        refresh_token="rt-456",
        client_id="client-123",
        client_secret="secret",
    )

    assert access_token == "at-new-789"
    assert expires_in == 3599


@pytest.mark.asyncio
async def test_refresh_calendar_access_token_invalid_grant_raises_reauth_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "invalid_grant",
                "error_description": "Token has been expired or revoked.",
            },
        )

    monkeypatch.setattr(
        "src.auth.calendar_oauth.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(CalendarReauthRequired):
        await refresh_calendar_access_token(
            refresh_token="rt-456",
            client_id="client-123",
            client_secret="secret",
        )
