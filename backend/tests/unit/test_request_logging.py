"""Tests for request lifecycle log lines emitted by request_id_middleware."""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_request_emits_start_log_line(capsys: pytest.CaptureFixture[str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/healthz")
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines() if l]
    events = [l["event"] for l in lines]
    assert "request.start" in events


@pytest.mark.asyncio
async def test_request_emits_end_log_line_with_status_and_ms(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/healthz")
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines() if l]
    end = next((l for l in lines if l["event"] == "request.end"), None)
    assert end is not None
    assert "status" in end["extra"]
    assert "ms" in end["extra"]
    assert end["extra"]["status"] == 200


@pytest.mark.asyncio
async def test_request_id_header_echoed_in_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz", headers={"X-Request-ID": "test-req-123"})
    assert resp.headers["x-request-id"] == "test-req-123"
