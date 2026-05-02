"""Dev utility: create a real HC user in parivarthan_dev and print JWT exports."""
import asyncio
import sys
import uuid
from pathlib import Path

# Add backend/ to sys.path so src.* imports work when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.auth.jwt_utils import create_access_token
from src.config import get_settings
from src.db.models import User


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        user = User(
            email=f"hc-verify-{uuid.uuid4().hex[:6]}@test.com",
            google_sub=f"g-verify-{uuid.uuid4().hex}",
            role="hc",
        )
        db.add(user)
        await db.flush()
        await db.commit()
        hc_id = str(user.id)

    await engine.dispose()

    token = create_access_token(
        sub=hc_id, role="hc", hc_id=hc_id,
        private_key=settings.jwt_private_key,
    )
    print(f"export HC_JWT={token}")
    print(f"export HC_ID={hc_id}")


asyncio.run(main())
