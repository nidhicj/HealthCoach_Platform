"""AWS S3 client using Signature Version 4. No boto3 (Pyodide-incompatible). Per Decision C."""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, datetime, timezone
from urllib.parse import quote
from uuid import UUID
from zoneinfo import ZoneInfo

from src.config import get_settings
from src.lib.http import make_http_client


def _sanitize(s: str, max_len: int = 40) -> str:
    return re.sub(r'[^A-Za-z0-9_.\-]', '_', s)[:max_len]


def _get_session_date_ist(scheduled_at: datetime) -> date:
    return scheduled_at.astimezone(ZoneInfo("Asia/Kolkata")).date()


def build_session_file_key(
    hc_user_id: UUID,
    client_code: str,
    client_full_name: str,
    session_date: date,
    session_number: int,
    filename: str,
) -> str:
    """
    Returns S3 key:
    hc-{hc_user_id}/client_session_library/{CP####}_{sanitized_name}/{YYYY-MM-DD}_session-{NN:02d}/{sanitized_filename}
    """
    sanitized_name = _sanitize(client_full_name)
    client_folder = f"{client_code}_{sanitized_name}"
    date_str = session_date.strftime("%Y-%m-%d")
    session_folder = f"{date_str}_session-{session_number:02d}"
    sanitized_file = _sanitize(filename, max_len=200)
    return f"hc-{hc_user_id}/client_session_library/{client_folder}/{session_folder}/{sanitized_file}"


# ── Sig V4 signing ────────────────────────────────────────────────────────────


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_signing_key(secret_key: str, date_str: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(f"AWS4{secret_key}".encode(), date_str)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "aws4_request")
    return k_signing


def _build_auth_header(
    method: str,
    bucket: str,
    region: str,
    key: str,
    payload: bytes,
    access_key: str,
    secret_key: str,
    extra_headers: dict[str, str] | None = None,
) -> tuple[dict[str, str], str]:
    """
    Returns (headers_dict, amz_date_str) where headers_dict includes
    Authorization, x-amz-content-sha256, and x-amz-date.
    """
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    host = f"{bucket}.s3.{region}.amazonaws.com"
    payload_hash = _sha256_hex(payload)

    # Canonical headers (must be sorted)
    headers: dict[str, str] = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if extra_headers:
        headers.update(extra_headers)

    sorted_header_names = sorted(headers.keys())
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted_header_names)
    signed_headers = ";".join(sorted_header_names)

    # URI encoding (key must be percent-encoded, slashes preserved)
    canonical_uri = "/" + quote(key, safe="/")
    canonical_querystring = ""  # no query params for PUT/DELETE/GET/HEAD

    canonical_request = "\n".join([
        method,
        canonical_uri,
        canonical_querystring,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])

    signing_key = _get_signing_key(secret_key, date_stamp, region, "s3")
    signature = _hmac_sha256(signing_key, string_to_sign).hex()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    result_headers = {
        "Authorization": authorization,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Host": host,
    }
    if extra_headers:
        result_headers.update(extra_headers)

    return result_headers, amz_date


# ── Public S3 operations ──────────────────────────────────────────────────────


async def s3_put(key: str, content: bytes, content_type: str) -> None:
    """Upload bytes to S3 at the given key."""
    settings = get_settings()
    bucket = settings.aws_s3_bucket_name
    region = settings.aws_region
    host = f"{bucket}.s3.{region}.amazonaws.com"
    url = f"https://{host}/{quote(key, safe='/')}"

    headers, _ = _build_auth_header(
        method="PUT",
        bucket=bucket,
        region=region,
        key=key,
        payload=content,
        access_key=settings.aws_access_key_id,
        secret_key=settings.aws_secret_access_key,
        extra_headers={"content-type": content_type},
    )
    headers["Content-Type"] = content_type

    async with make_http_client() as client:
        r = await client.put(url, content=content, headers=headers)
        r.raise_for_status()


async def s3_get(key: str) -> bytes:
    """Download bytes from S3 at the given key."""
    settings = get_settings()
    bucket = settings.aws_s3_bucket_name
    region = settings.aws_region
    host = f"{bucket}.s3.{region}.amazonaws.com"
    url = f"https://{host}/{quote(key, safe='/')}"

    headers, _ = _build_auth_header(
        method="GET",
        bucket=bucket,
        region=region,
        key=key,
        payload=b"",
        access_key=settings.aws_access_key_id,
        secret_key=settings.aws_secret_access_key,
    )

    async with make_http_client() as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.content


async def s3_delete(key: str) -> None:
    """Delete an object from S3 at the given key."""
    settings = get_settings()
    bucket = settings.aws_s3_bucket_name
    region = settings.aws_region
    host = f"{bucket}.s3.{region}.amazonaws.com"
    url = f"https://{host}/{quote(key, safe='/')}"

    headers, _ = _build_auth_header(
        method="DELETE",
        bucket=bucket,
        region=region,
        key=key,
        payload=b"",
        access_key=settings.aws_access_key_id,
        secret_key=settings.aws_secret_access_key,
    )

    async with make_http_client() as client:
        r = await client.delete(url, headers=headers)
        r.raise_for_status()


async def s3_exists(key: str) -> bool:
    """Return True if the S3 object exists (HEAD request)."""
    settings = get_settings()
    bucket = settings.aws_s3_bucket_name
    region = settings.aws_region
    host = f"{bucket}.s3.{region}.amazonaws.com"
    url = f"https://{host}/{quote(key, safe='/')}"

    headers, _ = _build_auth_header(
        method="HEAD",
        bucket=bucket,
        region=region,
        key=key,
        payload=b"",
        access_key=settings.aws_access_key_id,
        secret_key=settings.aws_secret_access_key,
    )

    async with make_http_client() as client:
        r = await client.head(url, headers=headers)
        return r.status_code == 200
