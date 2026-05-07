"""Dev utility: create or reuse an HC user in parivarthan_dev and print JWT exports.

Usage:
    python scripts/create_hc_user.py                        # random test email (old behaviour)
    python scripts/create_hc_user.py --email you@gmail.com  # upsert by email

If a user with that email already exists, reuses their ID and issues a fresh JWT.
If not, creates one with a placeholder google_sub so the mock test can run.

On first real Google OAuth login the auth router will find this row by email,
update google_sub to the real value, and everything links up automatically.
"""
import argparse
import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.auth.jwt_utils import create_access_token
from src.config import get_settings
from src.db.models import User


async def main(email: str | None) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is None:
                # Placeholder google_sub — will be replaced on first real OAuth login
                placeholder_sub = "pending-oauth-" + hashlib.sha256(email.encode()).hexdigest()[:16]
                user = User(email=email, google_sub=placeholder_sub, role="hc")
                db.add(user)
                await db.flush()
                await db.commit()
                print(f"# Created HC user: {email}", file=sys.stderr)
            else:
                print(f"# Reusing existing HC user: {email} (id={user.id})", file=sys.stderr)
        else:
            # Legacy random-email path (kept for backwards compat)
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
        ttl_seconds=24 * 3600,
    )
    print(f"export HC_JWT={token}")
    print(f"export HC_ID={hc_id}")


parser = argparse.ArgumentParser()
parser.add_argument("--email", default=None, help="Real email to create/reuse HC user")
args = parser.parse_args()
asyncio.run(main(args.email))
