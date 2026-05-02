"""Async DB + HTTP fixtures for integration tests. Uses parivarthan_test database."""
import os
import uuid
from collections.abc import AsyncGenerator
from uuid import UUID

# ── inject test credentials before any src.* module is imported ────────────────
# These are test-only keys — identical to the ones in tests/unit/test_jwt_utils.py
_TEST_PRIVATE_KEY = (
    "-----BEGIN EC PRIVATE KEY-----\n"
    "MHcCAQEEINUKf38U94IQoOq/dEoYsxyLqYjnOXC3GAqMWobTnzxSoAoGCCqGSM49\n"
    "AwEHoUQDQgAEnVbWIcXmEx/TyU/oblyoXtl8KrMqEapojcaWUflKuJ1QjIHjRCJg\n"
    "Dy9GhmB7ejifIIb7Z6zowO2fgHcRUMGSYg==\n"
    "-----END EC PRIVATE KEY-----"
)
_TEST_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEnVbWIcXmEx/TyU/oblyoXtl8KrMq\n"
    "EapojcaWUflKuJ1QjIHjRCJgDy9GhmB7ejifIIb7Z6zowO2fgHcRUMGSYg==\n"
    "-----END PUBLIC KEY-----"
)

os.environ.setdefault("JWT_PRIVATE_KEY", _TEST_PRIVATE_KEY)
os.environ.setdefault("JWT_PUBLIC_KEY", _TEST_PUBLIC_KEY)

# Clear any existing settings cache so the keys above take effect
try:
    from src.config import get_settings
    get_settings.cache_clear()
except Exception:  # noqa: BLE001
    pass

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import src.db.models  # noqa: F401 — registers all models with Base.metadata
from src.auth.jwt_utils import create_access_token
from src.config import get_settings
from src.db.base import Base
from src.db.models import Client, User


# ── engine (session-scoped: schema created once per pytest session) ────────────


@pytest.fixture(scope="session")
def db_url() -> str:
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres:localdevpassword@localhost:5432/parivarthan_test",
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest_asyncio.fixture(scope="session")
async def engine(db_url: str):  # type: ignore[no-untyped-def]
    eng = create_async_engine(db_url, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


# ── db (function-scoped: each test rolls back via connection-level transaction) ─


@pytest_asyncio.fixture()
async def db(engine) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[no-untyped-def]
    """
    Each test gets an isolated session. Uses a connection-level transaction +
    savepoint mode so that route handlers' commit() calls don't escape to disk —
    the outer rollback undoes everything at the end of the test.
    """
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


# ── HTTP client (function-scoped: overrides get_db with the test session) ──────


@pytest_asyncio.fixture()
async def http_client(db: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    from src.db.session import get_db
    from src.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ── JWT helpers ────────────────────────────────────────────────────────────────


def _make_jwt(user_id: UUID, role: str, hc_id: str | None) -> str:
    return create_access_token(
        sub=str(user_id),
        role=role,
        hc_id=hc_id,
        private_key=get_settings().jwt_private_key,
    )


def auth_headers(user_id: UUID, role: str, hc_id: str | None = None) -> dict[str, str]:
    token = _make_jwt(user_id, role, hc_id or str(user_id))
    return {"Authorization": f"Bearer {token}"}


# ── User fixtures ──────────────────────────────────────────────────────────────


async def _make_user(db: AsyncSession, role: str = "hc") -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@test.com",
        google_sub=f"g-{uuid.uuid4().hex}",
        role=role,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture()
async def hc_user(db: AsyncSession) -> User:
    return await _make_user(db, "hc")


@pytest_asyncio.fixture()
async def hc2_user(db: AsyncSession) -> User:
    return await _make_user(db, "hc")


@pytest.fixture()
def hc_headers(hc_user: User) -> dict[str, str]:
    return auth_headers(hc_user.id, "hc")


@pytest.fixture()
def hc2_headers(hc2_user: User) -> dict[str, str]:
    return auth_headers(hc2_user.id, "hc")


# ── Client user fixtures ───────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def client_user(db: AsyncSession) -> User:
    return await _make_user(db, "client")


@pytest_asyncio.fixture()
async def client_rec(db: AsyncSession, hc_user: User, client_user: User) -> Client:
    """A Client record linked to hc_user and client_user."""
    rec = Client(
        hc_user_id=hc_user.id,
        full_name="Test Client",
        user_id=client_user.id,
    )
    db.add(rec)
    await db.flush()
    return rec


@pytest.fixture()
def client_headers(hc_user: User, client_user: User) -> dict[str, str]:
    """JWT with role=client, sub=client_user.id, hc_id=hc_user.id."""
    return auth_headers(client_user.id, "client", hc_id=str(hc_user.id))
