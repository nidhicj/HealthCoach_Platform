import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_healthz_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_healthz_echoes_request_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz", headers={"X-Request-ID": "test-req-123"})
    assert response.headers.get("x-request-id") == "test-req-123"


@pytest.mark.asyncio
async def test_healthz_generates_request_id_if_missing():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) == 36  # UUID format
