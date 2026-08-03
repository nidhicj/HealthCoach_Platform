"""Root conftest for all tests (unit and integration).

Defines fixtures and hooks that apply across the entire test suite.
"""

import pytest

from src.lib.rate_limit import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """
    Reset slowapi's in-memory rate-limit storage before each test.

    Prevents test pollution: slowapi's storage is a process-global singleton,
    so limits would otherwise bleed from one test function to the next, and
    across unit/integration test boundaries. By placing this fixture at the
    root conftest level with autouse=True, it applies to all test functions
    in both tests/unit/ and tests/integration/ regardless of their location.
    """
    limiter.reset()
