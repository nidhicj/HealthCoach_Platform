"""One-off: backfill users.first_name/last_name for pilot HCs, ahead of Unit_006.

Temporary — see Unit_003 PHASE-01 Global Constraints. Run manually, once per HC,
against this worktree's tapas_dev database (port 5436).

Usage:
    python scripts/seed_hc_names.py <email> <first_name> <last_name>
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import get_settings
from src.db.models.users import User


async def main(email: str, first_name: str, last_name: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user found with email {email!r}")
            sys.exit(1)
        user.first_name = first_name
        user.last_name = last_name
        await db.commit()
        print(f"Set {email}: first_name={first_name!r} last_name={last_name!r}")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/seed_hc_names.py <email> <first_name> <last_name>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
