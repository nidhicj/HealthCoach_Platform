"""Dev utility: upsert a local dev HC's `hc_payment_accounts` row from
RAZORPAY_TEST_KEY_ID/RAZORPAY_TEST_KEY_SECRET/RAZORPAY_TEST_WEBHOOK_SECRET in
`.env`, so PHASE-05's payment flow can be tested end to end without first
clicking through the Settings > Payments connection form by hand.

LOCAL-DEV-ONLY CONVENIENCE. Production credentials only ever arrive through
the real connection flow (`POST /api/hc/payment-account/connect`,
`backend/src/api/payment_accounts.py`) — an HC pasting their own Razorpay
keys into the Settings UI. This script exists purely to save a few clicks in
a local dev loop; it is never invoked outside a developer's own machine (no
CI/deploy hook references it).

Mirrors `scripts/create_hc_user.py`'s convention: --email to select/require
the HC, `get_settings()` for env, a bare async SQLAlchemy session (no app
context needed), stderr for human-readable status, exit(1) on any failure
so it's script-loop-friendly.

Usage:
    python scripts/create_hc_user.py --email you@gmail.com   # first, if needed
    python scripts/seed_payment_account.py --email you@gmail.com

Same verify-then-store sequence as the real `connect_payment_account` handler
(`razorpay_client.verify_credentials`, then write `credentials`+`connected_at`)
— not skipped for this script, so a bad or expired `.env` triplet fails loudly
here instead of seeding a payment account that will only fail later, deep
inside a real checkout attempt.
"""
import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import get_settings
from src.db.models import HcPaymentAccount, User
from src.lib.razorpay_client import verify_credentials


async def main(email: str) -> None:
    settings = get_settings()

    missing = [
        name
        for name, value in (
            ("RAZORPAY_TEST_KEY_ID", settings.razorpay_test_key_id),
            ("RAZORPAY_TEST_KEY_SECRET", settings.razorpay_test_key_secret),
            ("RAZORPAY_TEST_WEBHOOK_SECRET", settings.razorpay_test_webhook_secret),
        )
        if not value
    ]
    if missing:
        print(f"# Missing from .env: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(
                f"# No user with email {email} — run scripts/create_hc_user.py "
                "--email first",
                file=sys.stderr,
            )
            await engine.dispose()
            sys.exit(1)

        # Same verify-before-store sequence as the real connect endpoint
        # (payment_accounts.py::connect_payment_account) — fail loudly here on
        # a bad/expired test-mode key pair rather than seeding a row that only
        # breaks later, inside an actual checkout attempt.
        try:
            verified = await verify_credentials(
                key_id=settings.razorpay_test_key_id,
                key_secret=settings.razorpay_test_key_secret,
            )
        except httpx.HTTPError as exc:
            print(f"# Could not reach Razorpay to verify test credentials: {exc}", file=sys.stderr)
            await engine.dispose()
            sys.exit(1)

        if not verified:
            print(
                "# RAZORPAY_TEST_KEY_ID/RAZORPAY_TEST_KEY_SECRET in .env did not verify "
                "against Razorpay — check they're correct and in test mode.",
                file=sys.stderr,
            )
            await engine.dispose()
            sys.exit(1)

        now = datetime.now(UTC)
        credentials = {
            "key_id": settings.razorpay_test_key_id,
            "key_secret": settings.razorpay_test_key_secret,
            "webhook_secret": settings.razorpay_test_webhook_secret,
        }

        account = (
            await db.execute(select(HcPaymentAccount).where(HcPaymentAccount.hc_user_id == user.id))
        ).scalar_one_or_none()

        if account is None:
            account = HcPaymentAccount(
                hc_user_id=user.id, credentials=credentials, connected_at=now
            )
            db.add(account)
            print(f"# Created hc_payment_accounts row for {email}", file=sys.stderr)
        else:
            # Reassign (not mutate in place) so SQLAlchemy's change tracking
            # sees a new value on this EncryptedJSON column and re-encrypts on
            # flush — same discipline as the real connect endpoint.
            account.credentials = credentials
            account.connected_at = now
            account.updated_at = now
            print(f"# Updated existing hc_payment_accounts row for {email}", file=sys.stderr)

        await db.commit()

    await engine.dispose()
    print(
        "# Done — this HC's Razorpay test credentials are now connected locally.",
        file=sys.stderr,
    )


parser = argparse.ArgumentParser()
parser.add_argument("--email", required=True, help="Email of the local dev HC user to connect")
args = parser.parse_args()
asyncio.run(main(args.email))
