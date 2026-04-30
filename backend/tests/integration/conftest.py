"""Async DB fixtures for integration tests. Uses parivarthan_test database."""
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
import src.db.models  # noqa: F401 — registers all models with Base.metadata


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


@pytest_asyncio.fixture()
async def db(engine) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
