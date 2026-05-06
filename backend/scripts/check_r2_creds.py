"""Diagnostic script — tests R2 credentials end-to-end before running the app.

Run from backend/:
    python scripts/check_r2_creds.py
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from src.config import get_settings
from src.lib.s3 import _build_auth_header, s3_delete, s3_get, s3_put

TEST_KEY = "_r2_cred_check/diagnostic_test_object.txt"
TEST_CONTENT = b"r2-credential-check-ok"


def _check(label: str, ok: bool, detail: str = "") -> None:
    symbol = "✓" if ok else "✗"
    print(f"  {symbol}  {label}", flush=True)
    if not ok:
        if detail:
            print(f"     {detail}")
        sys.exit(1)


async def _raw_put(s) -> None:
    """PUT using httpx directly with event hooks so we see every header sent."""
    import httpx
    from urllib.parse import quote

    bucket = s.r2_bucket_name
    account_id = s.r2_account_id
    host = f"{bucket}.{account_id}.r2.cloudflarestorage.com"
    url = f"https://{host}/{quote(TEST_KEY, safe='/')}"

    signed, _ = _build_auth_header(
        method="PUT",
        bucket=bucket,
        account_id=account_id,
        key=TEST_KEY,
        payload=TEST_CONTENT,
        access_key=s.r2_access_key_id,
        secret_key=s.r2_secret_access_key,
        extra_headers={"content-type": "text/plain"},
    )
    # content-type is already in signed headers via extra_headers — don't add again

    print("     Headers we will send:")
    for k, v in sorted(signed.items()):
        print(f"       {k}: {v}")

    async def log_request(request: httpx.Request) -> None:
        print("\n     Headers httpx actually sent:")
        for k, v in request.headers.items():
            print(f"       {k}: {v}")

    async with httpx.AsyncClient(event_hooks={"request": [log_request]}) as client:
        r = await client.put(url, content=TEST_CONTENT, headers=signed)
        print(f"\n     Response status : {r.status_code}")
        print(f"     Response body   : {r.text[:300]}")
        r.raise_for_status()


async def main() -> None:
    print("\nR2 credential diagnostic\n")

    print("Step 1 — env vars")
    s = get_settings()
    missing = [k for k, v in {
        "R2_ACCOUNT_ID":        s.r2_account_id,
        "R2_ACCESS_KEY_ID":     s.r2_access_key_id,
        "R2_SECRET_ACCESS_KEY": s.r2_secret_access_key,
        "R2_BUCKET_NAME":       s.r2_bucket_name,
    }.items() if not v.strip()]
    _check("all four R2 vars set", not missing,
           f"missing or empty: {', '.join(missing)}" if missing else "")
    print(f"     account_id  : {s.r2_account_id}")
    print(f"     bucket_name : {s.r2_bucket_name}")
    print(f"     access_key  : {s.r2_access_key_id}  ({len(s.r2_access_key_id)} chars)")
    print(f"     secret_key  : {s.r2_secret_access_key[:4]}…  ({len(s.r2_secret_access_key)} chars total)")

    print("\nStep 2 — PUT test object (full request trace)")
    try:
        await _raw_put(s)
        _check("PUT succeeded", True)
    except Exception as exc:
        _check("PUT succeeded", False, str(exc))

    print("\nStep 3 — GET test object back")
    try:
        body = await s3_get(TEST_KEY)
        _check("GET succeeded", True)
        _check("content matches", body == TEST_CONTENT,
               f"got {body!r}, expected {TEST_CONTENT!r}")
    except Exception as exc:
        _check("GET succeeded", False, str(exc))

    print("\nStep 4 — DELETE test object")
    try:
        await s3_delete(TEST_KEY)
        _check("DELETE succeeded", True)
    except Exception as exc:
        _check("DELETE succeeded", False, str(exc))

    print("\nAll checks passed — R2 credentials are correct.\n")


if __name__ == "__main__":
    asyncio.run(main())
