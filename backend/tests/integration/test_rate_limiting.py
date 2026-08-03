"""End-to-end tests for rate-limiting infrastructure via slowapi.

Tests verify:
1. The limiter module-level instance is properly wired
2. Rate limits return 429 when exceeded
3. Test fixture resets state between test functions (no bleed)
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_rate_limiter_enforces_limit(http_client: httpx.AsyncClient) -> None:
    """Verify that rate limit is enforced and returns 429 after limit exceeded."""
    # Make requests up to the limit (5 per hour)
    for i in range(5):
        response = await http_client.get("/health")
        assert response.status_code == 200, f"Request {i+1} failed with {response.status_code}"

    # 6th request should be rate-limited
    response = await http_client.get("/health")
    assert response.status_code == 429, f"Expected 429, got {response.status_code}"
    body = response.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_rate_limiter_limit_resets_between_tests_first(http_client: httpx.AsyncClient) -> None:
    """First test in a pair verifying reset fixture works. Make 3 requests."""
    for i in range(3):
        response = await http_client.get("/health")
        assert response.status_code == 200, f"Request {i+1} failed with {response.status_code}"
    # No assertion needed; we're just checking state doesn't leak to the next test


@pytest.mark.asyncio
async def test_rate_limiter_limit_resets_between_tests_second(http_client: httpx.AsyncClient) -> None:
    """Second test in a pair verifying reset fixture works.
    If reset fixture fails, this would hit the 3-request carry-over from the previous
    test and fail at request 2 or 3. With reset working, all 5 requests should succeed.
    """
    for i in range(5):
        response = await http_client.get("/health")
        assert response.status_code == 200, f"Request {i+1} failed after reset (would fail without reset); got {response.status_code}"
