"""Integration tests for session_notes S3 mirror on PATCH /sessions/{id}. P5 Part B."""
from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

import pytest


# ── S3 mirror tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_session_notes_calls_s3_put(
    http_client, hc_headers, session_id, db, client_rec
):
    """PATCH session_notes → s3_put called with the notes bytes and key containing session_notes.txt."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.sessions.s3_put", new_callable=AsyncMock) as mock_put:
        r = await http_client.patch(
            f"/api/sessions/{session_id}",
            headers=hc_headers,
            json={"session_notes": "My notes."},
        )

    assert r.status_code == 200, r.text
    mock_put.assert_awaited_once()

    # Inspect the call arguments: positional args are (key, content, content_type)
    call_args = mock_put.call_args
    key_arg = call_args.args[0]
    content_arg = call_args.args[1]
    content_type_arg = call_args.args[2]

    assert "session_notes.txt" in key_arg
    assert content_arg == b"My notes."
    assert content_type_arg == "text/plain"


@pytest.mark.asyncio
async def test_second_patch_overwrites_s3(
    http_client, hc_headers, session_id, db, client_rec
):
    """Two PATCHes → s3_put called twice; second call carries the updated notes."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.sessions.s3_put", new_callable=AsyncMock) as mock_put:
        await http_client.patch(
            f"/api/sessions/{session_id}",
            headers=hc_headers,
            json={"session_notes": "First version of notes."},
        )
        await http_client.patch(
            f"/api/sessions/{session_id}",
            headers=hc_headers,
            json={"session_notes": "Second version of notes."},
        )

    assert mock_put.await_count == 2
    second_call_content = mock_put.call_args_list[1].args[1]
    assert second_call_content == b"Second version of notes."


@pytest.mark.asyncio
async def test_s3_failure_does_not_fail_patch(
    http_client, hc_headers, session_id, db, client_rec
):
    """If s3_put raises an exception, PATCH still returns 200 and DB is updated."""
    client_rec.code = "CP0001"
    await db.flush()

    with patch("src.api.sessions.s3_put", new_callable=AsyncMock) as mock_put:
        mock_put.side_effect = RuntimeError("S3 unreachable")
        r = await http_client.patch(
            f"/api/sessions/{session_id}",
            headers=hc_headers,
            json={"session_notes": "Notes despite S3 failure."},
        )

    # PATCH must still succeed — DB is canonical, S3 is a mirror
    assert r.status_code == 200, r.text
    assert r.json()["session_notes"] == "Notes despite S3 failure."

    # Confirm DB has the new notes
    r2 = await http_client.get(f"/api/sessions/{session_id}", headers=hc_headers)
    assert r2.json()["session_notes"] == "Notes despite S3 failure."
