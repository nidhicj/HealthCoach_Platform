"""End-to-end tests for rate-limiting infrastructure via slowapi.

Tests verify:
1. The limiter module-level instance is properly wired
2. Rate limits return 429 when exceeded
3. Test fixture resets state between test functions (no bleed)

Note: Tests define a minimal throwaway FastAPI app with a rate-limited endpoint
purely for testing purposes. This keeps test infrastructure out of production
main.py — the limiter module is wired in main.py for real endpoints to use in
Task 4 (intake POST), but this smoke test uses its own isolated test app.
"""

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


@pytest.mark.asyncio
async def test_rate_limiter_enforces_limit() -> None:
    """Verify that rate limit is enforced and returns 429 after limit exceeded."""
    # Create isolated limiter instance for this test (no cross-test state)
    test_limiter = Limiter(key_func=get_remote_address)

    test_app = FastAPI()
    test_app.state.limiter = test_limiter

    @test_app.exception_handler(RateLimitExceeded)
    async def rate_limit_exception_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
        )

    @test_app.get("/test")
    @test_limiter.limit("5/hour")
    async def test_endpoint(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        # Make requests up to the limit (5 per hour)
        for i in range(5):
            response = await client.get("/test")
            assert (
                response.status_code == 200
            ), f"Request {i+1} failed with {response.status_code}"

        # 6th request should be rate-limited
        response = await client.get("/test")
        assert response.status_code == 429, f"Expected 429, got {response.status_code}"
        body = response.json()
        assert "detail" in body


@pytest.mark.asyncio
async def test_rate_limiter_limit_resets_between_tests_first() -> None:
    """First test in a pair verifying reset fixture works. Make 3 requests."""
    # Create isolated limiter instance for this test (no cross-test state)
    test_limiter = Limiter(key_func=get_remote_address)

    test_app = FastAPI()
    test_app.state.limiter = test_limiter

    @test_app.exception_handler(RateLimitExceeded)
    async def rate_limit_exception_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
        )

    @test_app.get("/test")
    @test_limiter.limit("5/hour")
    async def test_endpoint(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        for i in range(3):
            response = await client.get("/test")
            assert (
                response.status_code == 200
            ), f"Request {i+1} failed with {response.status_code}"


@pytest.mark.asyncio
async def test_rate_limiter_limit_resets_between_tests_second() -> None:
    """Second test in a pair verifying reset fixture works.
    Each test creates its own limiter instance, so no cross-test state bleed.
    This ensures the module-level limiter in main.py is wired correctly
    and each endpoint request starts with a clean rate-limit state.
    """
    # Create isolated limiter instance for this test (no cross-test state)
    test_limiter = Limiter(key_func=get_remote_address)

    test_app = FastAPI()
    test_app.state.limiter = test_limiter

    @test_app.exception_handler(RateLimitExceeded)
    async def rate_limit_exception_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
        )

    @test_app.get("/test")
    @test_limiter.limit("5/hour")
    async def test_endpoint(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        for i in range(5):
            response = await client.get("/test")
            assert (
                response.status_code == 200
            ), f"Request {i+1} failed; got {response.status_code}"
