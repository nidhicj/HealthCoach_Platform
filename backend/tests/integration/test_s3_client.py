"""Unit-style tests for s3.py key builder and signing helpers. No DB/HTTP client needed."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lib.s3 import _sanitize, build_session_file_key, s3_delete, s3_put


# ── Key builder tests ─────────────────────────────────────────────────────────


def test_build_session_file_key_correct_structure():
    """build_session_file_key produces the expected path structure."""
    import uuid
    hc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    key = build_session_file_key(
        hc_id,
        "CP0001",
        "Test Client",
        date(2026, 6, 1),
        1,
        "report.pdf",
    )
    # e.g. hc-12345678-1234-5678-1234-567812345678/client_session_library/CP0001_Test_Client/2026-06-01_session-01/report.pdf
    assert key.startswith(f"hc-{hc_id}/client_session_library/CP0001_Test_Client/2026-06-01_session-01/report.pdf")


def test_build_session_file_key_sanitizes_special_chars():
    """Filenames with spaces and slashes are sanitized to underscores."""
    import uuid
    hc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    key = build_session_file_key(
        hc_id,
        "CP0002",
        "Some Client",
        date(2026, 7, 15),
        3,
        "my file/with spaces.txt",
    )
    # The sanitized filename segment should not contain spaces or slashes
    filename_segment = key.split("/")[-1]
    assert " " not in filename_segment
    assert "/" not in filename_segment
    # Slashes and spaces become underscores
    assert "my_file_with_spaces.txt" == filename_segment


def test_sanitize_replaces_disallowed_chars():
    """_sanitize replaces anything not in [A-Za-z0-9_.-] with underscores and clips to max_len."""
    result = _sanitize("Test Client Name", max_len=20)
    # Spaces become underscores; result is 16 chars, not clipped
    assert result == "Test_Client_Name"
    assert len(result) <= 20

    long_str = "A" * 50
    clipped = _sanitize(long_str, max_len=20)
    assert len(clipped) == 20

    special = _sanitize("hello world/foo:bar?baz")
    assert " " not in special
    assert "/" not in special
    assert ":" not in special
    assert "?" not in special


# ── s3_put signs the request ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_s3_put_sends_auth_header():
    """s3_put builds an Authorization header that starts with AWS4-HMAC-SHA256."""
    captured_headers: dict[str, str] = {}

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    async def fake_put(url, *, content, headers, **kwargs):
        captured_headers.update(headers)
        return mock_resp

    mock_client.put = fake_put

    with patch("src.lib.s3.get_settings") as mock_settings:
        mock_settings.return_value.r2_access_key_id = "AKIAIOSFODNN7EXAMPLE"
        mock_settings.return_value.r2_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        mock_settings.return_value.r2_bucket_name = "test-bucket"
        mock_settings.return_value.r2_account_id = "abc123testaccountid"

        with patch("src.lib.s3.make_http_client", return_value=mock_client):
            await s3_put("test/key.txt", b"hello world", "text/plain")

    assert "Authorization" in captured_headers
    assert captured_headers["Authorization"].startswith("AWS4-HMAC-SHA256 ")


@pytest.mark.asyncio
async def test_s3_delete_sends_auth_header():
    """s3_delete builds a signed Authorization header (AWS4-HMAC-SHA256)."""
    captured_headers: dict[str, str] = {}

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    async def fake_delete(url, *, headers, **kwargs):
        captured_headers.update(headers)
        return mock_resp

    mock_client.delete = fake_delete

    with patch("src.lib.s3.get_settings") as mock_settings:
        mock_settings.return_value.r2_access_key_id = "AKIAIOSFODNN7EXAMPLE"
        mock_settings.return_value.r2_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        mock_settings.return_value.r2_bucket_name = "test-bucket"
        mock_settings.return_value.r2_account_id = "abc123testaccountid"

        with patch("src.lib.s3.make_http_client", return_value=mock_client):
            await s3_delete("test/key.txt")

    assert "Authorization" in captured_headers
    assert captured_headers["Authorization"].startswith("AWS4-HMAC-SHA256 ")
