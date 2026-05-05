"""Integration tests for file upload/list/delete endpoints. P5 Part B."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.api.files import MAX_FILE_SIZE_BYTES


# ── Upload tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_single_file_creates_row(
    http_client, hc_headers, session_id, db, client_rec
):
    """POST a single text file → 201, row appears in GET /files."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.files.s3_put", new_callable=AsyncMock) as mock_put:
        r = await http_client.post(
            f"/api/sessions/{session_id}/files",
            headers=hc_headers,
            files=[("files", ("notes.txt", b"hello world", "text/plain"))],
        )

    assert r.status_code == 201, r.text
    mock_put.assert_awaited_once()

    body = r.json()
    assert len(body) == 1
    assert body[0]["original_filename"] == "notes.txt"
    assert body[0]["mime_type"] == "text/plain"
    assert body[0]["size_bytes"] == len(b"hello world")

    # Verify via GET
    r2 = await http_client.get(f"/api/sessions/{session_id}/files", headers=hc_headers)
    assert r2.status_code == 200
    items = r2.json()
    assert len(items) == 1
    assert items[0]["original_filename"] == "notes.txt"


@pytest.mark.asyncio
async def test_upload_multi_file_creates_all_rows(
    http_client, hc_headers, session_id, db, client_rec
):
    """POST two files → both rows appear in GET /files."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.files.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/sessions/{session_id}/files",
            headers=hc_headers,
            files=[
                ("files", ("file1.txt", b"content one", "text/plain")),
                ("files", ("file2.md", b"content two", "text/markdown")),
            ],
        )

    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body) == 2
    filenames = {f["original_filename"] for f in body}
    assert filenames == {"file1.txt", "file2.md"}

    r2 = await http_client.get(f"/api/sessions/{session_id}/files", headers=hc_headers)
    assert len(r2.json()) == 2


@pytest.mark.asyncio
async def test_upload_file_over_25mb_returns_400(
    http_client, hc_headers, session_id, db, client_rec
):
    """POST with content > 25 MB → 400."""
    client_rec.code = "CP0001"
    await db.flush()

    # Patch MAX_FILE_SIZE_BYTES to a small value so the test is fast
    tiny_limit = 100
    with patch("src.api.files.MAX_FILE_SIZE_BYTES", tiny_limit):
        with patch("src.api.files.s3_put", new_callable=AsyncMock):
            r = await http_client.post(
                f"/api/sessions/{session_id}/files",
                headers=hc_headers,
                files=[("files", ("big.txt", b"x" * (tiny_limit + 1), "text/plain"))],
            )

    assert r.status_code == 400, r.text
    assert "25 MB" in r.json()["detail"] or "limit" in r.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_mime_returns_400(
    http_client, hc_headers, session_id, db, client_rec
):
    """POST with unsupported Content-Type → 400."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.files.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/sessions/{session_id}/files",
            headers=hc_headers,
            files=[("files", ("photo.png", b"\x89PNG\r\n", "image/png"))],
        )

    assert r.status_code == 400, r.text
    assert "Unsupported" in r.json()["detail"] or "file type" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_cross_tenant_returns_404(
    http_client, hc2_headers, session_id, db, client_rec
):
    """POST by the wrong HC returns 404 (session not owned by hc2)."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.files.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/sessions/{session_id}/files",
            headers=hc2_headers,
            files=[("files", ("notes.txt", b"steal", "text/plain"))],
        )

    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_delete_file_removes_row_and_is_idempotent(
    http_client, hc_headers, session_id, db, client_rec
):
    """DELETE removes the row; second DELETE returns 404."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.files.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/sessions/{session_id}/files",
            headers=hc_headers,
            files=[("files", ("delete_me.txt", b"bye", "text/plain"))],
        )
    assert r.status_code == 201
    file_id = r.json()[0]["id"]

    with patch("src.api.files.s3_delete", new_callable=AsyncMock):
        r2 = await http_client.delete(
            f"/api/sessions/{session_id}/files/{file_id}",
            headers=hc_headers,
        )
    assert r2.status_code == 204

    # Row is gone from GET
    r3 = await http_client.get(f"/api/sessions/{session_id}/files", headers=hc_headers)
    assert r3.json() == []

    # Second DELETE → 404
    with patch("src.api.files.s3_delete", new_callable=AsyncMock):
        r4 = await http_client.delete(
            f"/api/sessions/{session_id}/files/{file_id}",
            headers=hc_headers,
        )
    assert r4.status_code == 404


@pytest.mark.asyncio
async def test_delete_s3_failure_still_removes_db_row(
    http_client, hc_headers, session_id, db, client_rec
):
    """S3 delete failure does not block DB row removal (DB canonical, S3 best-effort)."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.files.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/sessions/{session_id}/files",
            headers=hc_headers,
            files=[("files", ("fail.txt", b"content", "text/plain"))],
        )
    assert r.status_code == 201
    file_id = r.json()[0]["id"]

    with patch("src.api.files.s3_delete", side_effect=RuntimeError("S3 unavailable")):
        r2 = await http_client.delete(
            f"/api/sessions/{session_id}/files/{file_id}",
            headers=hc_headers,
        )
    assert r2.status_code == 204

    # DB row is gone even though S3 failed
    r3 = await http_client.get(f"/api/sessions/{session_id}/files", headers=hc_headers)
    assert r3.json() == []


@pytest.mark.asyncio
async def test_upload_zoom_filename_autodetects_is_zoom_summary(
    http_client, hc_headers, session_id, db, client_rec
):
    """Filename starting with zoom_ai_summary_ auto-sets is_zoom_summary=True."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.files.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/sessions/{session_id}/files",
            headers=hc_headers,
            files=[("files", ("zoom_ai_summary_meeting.txt", b"transcript", "text/plain"))],
        )

    assert r.status_code == 201, r.text
    assert r.json()[0]["is_zoom_summary"] is True
