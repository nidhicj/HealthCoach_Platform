"""Integration tests: GET /api/upload/:token (public, unauthenticated, PHASE-03
Task 5) and POST /api/upload/:token/files (blood report upload + brief
generation, PHASE-03 Task 6)."""
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Lead, LeadFile, LeadUploadToken, User

pytestmark = pytest.mark.asyncio


async def _make_lead(db: AsyncSession, hc_user: User) -> Lead:
    lead = Lead(
        hc_user_id=hc_user.id,
        full_name="Jane Doe",
        email=f"jane-{uuid.uuid4().hex[:8]}@example.com",
        status="tests_recommended",
    )
    db.add(lead)
    await db.flush()
    return lead


async def _make_token(
    db: AsyncSession,
    lead: Lead,
    *,
    used_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> str:
    """Creates a LeadUploadToken row and returns the raw (pre-hash) token."""
    raw_token = os.urandom(32).hex()
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db.add(LeadUploadToken(
        lead_id=lead.id,
        token_hash=token_hash,
        used_at=used_at,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=14)),
    ))
    await db.flush()
    return raw_token


async def test_valid_token_returns_200_with_only_hc_name(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.flush()
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)

    # No Authorization header at all — this is a public endpoint.
    resp = await http_client.get(f"/api/upload/{raw_token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["state"] == "valid"
    assert body["hc_name"] == "Asha Rao"
    # Core security property: no Lead PII, no questionnaire data — allowlisted
    # response contains only {state, message, hc_name}, and message is null here.
    assert set(body.keys()) == {"state", "message", "hc_name"}
    assert body["message"] is None


async def test_nonexistent_token_returns_200_not_found_state(http_client: AsyncClient):
    resp = await http_client.get("/api/upload/this-token-does-not-exist-at-all")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["state"] == "not_found"
    assert body["hc_name"] is None
    assert body["message"] == (
        "This upload link is invalid. Please contact your health coach for a new link."
    )


async def test_used_token_returns_200_used_state_with_spec_message(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead, used_at=datetime.now(UTC) - timedelta(hours=1))

    resp = await http_client.get(f"/api/upload/{raw_token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["state"] == "used"
    assert body["hc_name"] is None
    assert body["message"] == (
        "Your reports have already been uploaded successfully. No further action needed."
    )


async def test_expired_token_returns_200_expired_state_with_spec_message_and_hc_name(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.flush()
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(
        db, lead, expires_at=datetime.now(UTC) - timedelta(days=1)
    )

    resp = await http_client.get(f"/api/upload/{raw_token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["state"] == "expired"
    assert body["message"] == "This upload link has expired. Please contact Asha Rao for a new link."
    # Only the "valid" state exposes a top-level hc_name — for "expired" the name
    # is embedded in `message` only, per the task's "valid -> hc_name ONLY" scope.
    assert body["hc_name"] is None


async def test_used_takes_precedence_over_expired_when_both_true(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """A token that is both past its expiry and already used must report "used" —
    matches the check order in src.auth.router._verify_invite (used checked before
    expired) and this endpoint's own documented order."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(
        db,
        lead,
        used_at=datetime.now(UTC) - timedelta(hours=1),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    resp = await http_client.get(f"/api/upload/{raw_token}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "used"


async def test_raw_token_is_never_matched_directly_only_via_hash(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """Sanity check that lookup goes through the SHA-256 hash, not a raw-token
    column — passing the *hash* itself as the path token must not match."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    resp = await http_client.get(f"/api/upload/{token_hash}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "not_found"


# ── POST /api/upload/:token/files — PHASE-03 Task 6 ──────────────────────────
#
# File-content fixtures. `_valid_pdf_with_text` is a hand-built (not
# pypdf-generated) but genuinely pypdf-parseable PDF — verified interactively
# against `pypdf.PdfReader` before writing these tests — so tests exercising the
# real `extract_text()`/`generate_lead_brief()` pipeline get real extracted text,
# not just a blank page. `_CORRUPT_PDF_BYTES` passes `sniff_mime` (starts with
# `%PDF`) but is not valid PDF structure — confirmed interactively to make
# `pypdf.PdfReader` raise `PdfStreamError`, which is exactly the "magic bytes
# say PDF, but unparseable" gap this endpoint's extract_text try/except exists
# to handle gracefully.


def _valid_pdf_with_text() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"5 0 obj<</Length 44>>\nstream\nBT /F1 12 Tf 20 100 Td (Hemoglobin 13.5) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF"
    )


_CORRUPT_PDF_BYTES = b"%PDF-1.4\n" + b"not a real pdf structure at all" * 5
_JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
_UNRECOGNIZED_BYTES = b"MZ" + b"\x00" * 32  # DOS/EXE header — not PDF/JPEG/PNG

_VALID_LEAD_BRIEF_JSON = json.dumps({
    "questionnaire_findings": "Lead reports low energy and irregular sleep.",
    "blood_report_highlights": "Hemoglobin within normal range.",
    "suggested_discussion_points": ["Discuss sleep hygiene"],
    "flags": [],
})


def _mock_http(content: str, model: str = "meta-llama/llama-3.3-70b-instruct:free") -> AsyncMock:
    """Same helper pattern as test_lead_brief_generation.py — mocks the OpenRouter
    HTTP call so the *real* generate_lead_brief()/write_llm_call() pipeline runs
    end-to-end, producing a genuine `llm_calls` row (needed since
    `leads.brief_llm_call_id` is a real FK)."""
    response_data = {
        "id": "gen-upload-test-abc123",
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 90},
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_data
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_resp)
    return mock_http


async def test_successful_multi_file_upload_generates_brief_and_notifies_hc(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """Happy path: two accepted files (one PDF, one JPEG) upload successfully,
    the real generate_lead_brief() pipeline runs (mocked only at the OpenRouter
    HTTP boundary) and succeeds, and the HC's "brief ready" email fires — not the
    "failed" one."""
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.flush()
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [
        ("files", ("report.pdf", _valid_pdf_with_text(), "application/pdf")),
        ("files", ("photo.jpg", _JPEG_BYTES, "image/jpeg")),
    ]

    mock_http = _mock_http(_VALID_LEAD_BRIEF_JSON)
    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put,
        patch("src.llm_service.client.make_http_client", return_value=mock_http),
        patch("src.api.upload.send_lead_brief_ready_email") as mock_ready_email,
        patch("src.api.upload.send_lead_brief_failed_email") as mock_failed_email,
    ):
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 201, resp.text
    assert "message" in resp.json()
    assert mock_put.await_count == 2

    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert len(lead_files) == 2
    mimes = {lf.mime_type for lf in lead_files}
    assert mimes == {"application/pdf", "image/jpeg"}
    for lf in lead_files:
        assert lf.s3_key.startswith(f"leads/{lead.id}/reports/")
        assert lf.hc_user_id == hc_user.id
        assert lf.purpose == "blood_report"

    token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead.id)
    )).scalar_one()
    assert token_row.used_at is not None

    assert lead.status == "report_uploaded"
    assert lead.brief_text is not None
    assert lead.brief_llm_call_id is not None

    llm_call_row = (await db.execute(sa.text(
        "SELECT use_case, error_message FROM llm_calls WHERE id = :id"
    ), {"id": lead.brief_llm_call_id})).first()
    assert llm_call_row is not None
    assert llm_call_row.use_case == "lead_brief"
    assert llm_call_row.error_message is None

    mock_ready_email.assert_called_once()
    kwargs = mock_ready_email.call_args.kwargs
    assert kwargs["to"] == hc_user.email
    assert kwargs["hc_name"] == "Asha Rao"
    assert kwargs["lead_name"] == lead.full_name
    assert kwargs["lead_detail_link"].endswith(f"/leads/{lead.id}")
    mock_failed_email.assert_not_called()


async def test_magic_byte_sniffing_overrides_misleading_filename_and_content_type(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """A real PDF uploaded with a `.jpg` filename and an `image/jpeg`
    Content-Type must still be classified (and stored) as `application/pdf` —
    proves classification is genuinely magic-byte based, not filename/header
    based."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [("files", ("scan.jpg", _valid_pdf_with_text(), "image/jpeg"))]

    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock),
        patch(
            "src.llm_service.generate_lead_brief", new_callable=AsyncMock,
            return_value=(None, None),
        ),
        patch("src.api.upload.send_lead_brief_failed_email"),
    ):
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 201, resp.text
    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert len(lead_files) == 1
    assert lead_files[0].mime_type == "application/pdf"
    assert lead_files[0].filename == "scan.jpg"


async def test_unrecognized_file_in_batch_rejects_whole_batch_before_any_r2_write(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """One genuinely valid PDF plus one unrecognized (.exe magic bytes) file in
    the same batch must reject the WHOLE batch — including the valid file — and
    must do so before any `s3_put()` call, not after uploading the valid one."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [
        ("files", ("good.pdf", _valid_pdf_with_text(), "application/pdf")),
        ("files", ("bad.exe", _UNRECOGNIZED_BYTES, "application/octet-stream")),
    ]

    with patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put:
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 422, resp.text
    mock_put.assert_not_called()

    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert lead_files == []

    token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead.id)
    )).scalar_one()
    assert token_row.used_at is None
    await db.refresh(lead)
    assert lead.status == "tests_recommended"


async def test_r2_failure_midbatch_leaves_token_unused_and_no_leadfile_rows(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """s3_put() raises on the 2nd of 3 files. Must leave: no LeadFile rows
    committed for ANY file (including the one that succeeded before the
    failure), the token still unused, and the lead's status untouched — so the
    Lead can retry with the same link."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [
        ("files", ("one.pdf", _valid_pdf_with_text(), "application/pdf")),
        ("files", ("two.pdf", _valid_pdf_with_text(), "application/pdf")),
        ("files", ("three.pdf", _valid_pdf_with_text(), "application/pdf")),
    ]

    call_count = 0

    async def _flaky_put(key: str, content: bytes, content_type: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("R2 outage")

    with patch(
        "src.api.upload.s3_put", new_callable=AsyncMock, side_effect=_flaky_put
    ) as mock_put:
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 503, resp.text
    # Sequential (D-5): the 3rd file's s3_put is never attempted once the 2nd fails.
    assert mock_put.await_count == 2

    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert lead_files == []

    token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead.id)
    )).scalar_one()
    assert token_row.used_at is None
    await db.refresh(lead)
    assert lead.status == "tests_recommended"


async def test_brief_generation_failure_still_reports_upload_success_and_sends_failed_email(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """generate_lead_brief() returns (None, None) (its documented failure signal
    — never an exception). Decision D-2: the HTTP response must still report
    upload success, leads.status must still have advanced to "report_uploaded"
    (already committed before brief generation ran), and the HC gets the
    "brief failed" email instead of "brief ready"."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [("files", ("report.pdf", _valid_pdf_with_text(), "application/pdf"))]

    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock),
        patch(
            "src.llm_service.generate_lead_brief", new_callable=AsyncMock,
            return_value=(None, None),
        ) as mock_gen,
        patch("src.api.upload.send_lead_brief_failed_email") as mock_failed_email,
        patch("src.api.upload.send_lead_brief_ready_email") as mock_ready_email,
    ):
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 201, resp.text
    assert resp.json()["message"]  # generic success confirmation, unaffected by brief outcome
    mock_gen.assert_awaited_once()

    assert lead.status == "report_uploaded"
    assert lead.brief_text is None
    assert lead.brief_llm_call_id is None

    mock_failed_email.assert_called_once()
    mock_ready_email.assert_not_called()


async def test_unextractable_pdf_yields_empty_text_but_upload_and_brief_still_proceed(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """A file that passes MIME sniffing (starts with `%PDF`) but is not valid PDF
    structure must not crash the endpoint — extract_text()'s failure is caught
    and treated as an empty-text "gap", and the upload + brief attempt proceed
    normally (empty blood_report_text is itself a documented-safe input to
    generate_lead_brief(), per Task 3)."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [("files", ("corrupt.pdf", _CORRUPT_PDF_BYTES, "application/pdf"))]

    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock),
        patch(
            "src.llm_service.generate_lead_brief", new_callable=AsyncMock,
            return_value=("BRIEF TEXT", None),
        ) as mock_gen,
        patch("src.api.upload.send_lead_brief_ready_email"),
    ):
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 201, resp.text
    mock_gen.assert_awaited_once()
    assert mock_gen.call_args.kwargs["blood_report_text"] == ""

    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert len(lead_files) == 1
    assert lead_files[0].mime_type == "application/pdf"


async def test_post_to_used_token_returns_same_state_shape_as_get_no_upload_processed(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead, used_at=datetime.now(UTC) - timedelta(hours=1))
    await db.commit()

    with patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put:
        resp = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[("files", ("report.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "used"
    assert body["message"] == (
        "Your reports have already been uploaded successfully. No further action needed."
    )
    mock_put.assert_not_called()
    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert lead_files == []


async def test_post_to_expired_token_returns_same_state_shape_as_get_no_upload_processed(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.flush()
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead, expires_at=datetime.now(UTC) - timedelta(days=1))
    await db.commit()

    with patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put:
        resp = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[("files", ("report.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "expired"
    assert body["message"] == (
        "This upload link has expired. Please contact Asha Rao for a new link."
    )
    mock_put.assert_not_called()
    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert lead_files == []


async def test_post_to_nonexistent_token_returns_same_state_shape_as_get(
    http_client: AsyncClient,
):
    with patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put:
        resp = await http_client.post(
            "/api/upload/this-token-does-not-exist-at-all/files",
            files=[("files", ("report.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "not_found"
    assert body["message"] == (
        "This upload link is invalid. Please contact your health coach for a new link."
    )
    mock_put.assert_not_called()


async def test_too_many_files_rejected_before_any_r2_write(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [
        ("files", (f"f{i}.pdf", _valid_pdf_with_text(), "application/pdf")) for i in range(6)
    ]
    with patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put:
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 422, resp.text
    mock_put.assert_not_called()

    token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead.id)
    )).scalar_one()
    assert token_row.used_at is None


async def test_oversized_single_file_rejected_before_any_r2_write(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    with (
        patch("src.api.upload._MAX_FILE_SIZE_BYTES", 100),
        patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put,
    ):
        resp = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[("files", ("big.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )

    assert resp.status_code == 422, resp.text
    mock_put.assert_not_called()


async def test_oversized_total_batch_rejected_before_any_r2_write(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    with (
        patch("src.api.upload._MAX_TOTAL_SIZE_BYTES", 200),  # smaller than 2 files combined
        patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put,
    ):
        resp = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[
                ("files", ("a.pdf", _valid_pdf_with_text(), "application/pdf")),
                ("files", ("b.pdf", _valid_pdf_with_text(), "application/pdf")),
            ],
        )

    assert resp.status_code == 422, resp.text
    mock_put.assert_not_called()


async def test_second_commit_failure_still_reports_upload_success(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """Finding 1 (Critical, task-6 review): the second `db.commit()` — the one
    that persists brief_text/brief_llm_call_id (or, on brief failure, the
    llm_calls audit row) — must be guarded. If IT fails (simulated here as the
    2nd of the request's two `db.commit()` calls raising), the Lead's upload
    has already durably succeeded (LeadFile rows + used_at + status committed
    in the FIRST commit) and the HTTP response must still report success, not
    a bare 500 for an upload that actually worked and whose token is now
    unrecoverably consumed."""
    lead = await _make_lead(db, hc_user)
    lead_id = lead.id  # captured before the request — see note below
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [("files", ("report.pdf", _valid_pdf_with_text(), "application/pdf"))]

    commit_calls = 0
    original_commit = AsyncSession.commit

    async def _flaky_commit(self: AsyncSession) -> None:
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise RuntimeError("simulated transient DB error on brief-persist commit")
        await original_commit(self)

    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock),
        patch(
            "src.llm_service.generate_lead_brief", new_callable=AsyncMock,
            return_value=("BRIEF TEXT", uuid.uuid4()),
        ),
        patch("src.api.upload.send_lead_brief_ready_email") as mock_ready_email,
        patch("src.api.upload.send_lead_brief_failed_email") as mock_failed_email,
        patch.object(AsyncSession, "commit", _flaky_commit),
    ):
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 201, resp.text
    assert resp.json()["message"]
    assert commit_calls == 2  # proves the 2nd (guarded) commit really ran and really failed

    # This test's `db` is the SAME session the app used (dependency-overridden,
    # per tests/integration/conftest.py) — the router's own `db.rollback()`
    # (triggered by the simulated commit failure) expires every object that
    # session was tracking, `lead` included. Query by the plain `lead_id`
    # captured above (not `lead.id`) to avoid synchronously touching an
    # expired attribute outside an awaited ORM call, which raises
    # `MissingGreenlet` under SQLAlchemy's async engine.
    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead_id)
    )).scalars().all()
    assert len(lead_files) == 1
    token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead_id)
    )).scalar_one()
    assert token_row.used_at is not None
    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.status == "report_uploaded"

    # Since the persist-commit failed, "ready" must NOT fire (brief_text was
    # never actually saved) — "failed" fires instead, per the fix's design.
    mock_ready_email.assert_not_called()
    mock_failed_email.assert_called_once()


async def test_brief_failure_commits_llm_calls_audit_row(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """Finding 2 (Important, task-6 review): the `(None, None)` "brief
    generation failed" branch must still commit, or the `llm_calls` row
    `write_llm_call()` wrote (flush-only, per its own contract) is silently
    rolled back when the request's session closes — losing PHASE-03 D-1's
    required audit trail for why the brief failed. Exercises the REAL
    generate_lead_brief()/write_llm_call() pipeline (mocked only at the
    OpenRouter HTTP boundary) so the llm_calls row is genuinely written, not
    asserted via a mock."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    files_payload = [("files", ("report.pdf", _valid_pdf_with_text(), "application/pdf"))]

    # A malformed (non-JSON) LLM response — generate_lead_brief's documented
    # failure path: returns (None, None) and records the failure via
    # write_llm_call(error_message=...).
    mock_http = _mock_http("not valid json at all")
    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock),
        patch("src.llm_service.client.make_http_client", return_value=mock_http),
        patch("src.api.upload.send_lead_brief_failed_email") as mock_failed_email,
    ):
        resp = await http_client.post(f"/api/upload/{raw_token}/files", files=files_payload)

    assert resp.status_code == 201, resp.text
    mock_failed_email.assert_called_once()

    await db.refresh(lead)
    assert lead.brief_text is None
    assert lead.brief_llm_call_id is None

    # The critical assertion: query llm_calls directly for a row belonging to
    # this lead's brief attempt. `llm_calls` has no `lead_id` column (per
    # src/db/models/llm.py) — correlate via `hc_user_id` + `use_case`
    # instead, same as `write_llm_call()`'s own recorded fields; this test's
    # `hc_user` fixture is exclusive to this test's isolated transaction. If
    # the fix's commit didn't run, this row was flushed then silently rolled
    # back and will not be found here.
    llm_call_row = (await db.execute(sa.text(
        "SELECT use_case, error_message FROM llm_calls "
        "WHERE hc_user_id = :hc_user_id AND use_case = 'lead_brief' "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"hc_user_id": str(hc_user.id)})).first()
    assert llm_call_row is not None, (
        "llm_calls row for the failed brief attempt was not committed — "
        "Finding 2 regression"
    )
    assert llm_call_row.error_message is not None


async def test_second_post_against_already_used_token_returns_used_not_a_second_upload(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """Finding 3 (Important, task-6 review): concurrency-oriented coverage.
    This test harness runs every request in a test against a single shared
    DB session/connection (see tests/integration/conftest.py's `db` fixture),
    so a genuine two-connections-racing-on-FOR-UPDATE test isn't possible
    here. This test instead exercises the practical, harness-compatible
    proxy the task brief calls out as the minimum bar: two sequential POSTs
    against the same token, the first consuming it, the second must be
    rejected as "used" rather than processing a second upload batch — proving
    the token, once consumed, can never be consumed again regardless of how
    many requests arrive for it."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put,
        patch(
            "src.llm_service.generate_lead_brief", new_callable=AsyncMock,
            return_value=(None, None),
        ),
        patch("src.api.upload.send_lead_brief_failed_email"),
    ):
        first = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[("files", ("one.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )
        assert first.status_code == 201, first.text
        assert mock_put.await_count == 1

        second = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[("files", ("two.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )

    assert second.status_code == 200, second.text
    assert second.json()["state"] == "used"
    # Still only 1 s3_put ever — the second request never touched R2.
    assert mock_put.await_count == 1

    lead_files = (await db.execute(
        select(LeadFile).where(LeadFile.lead_id == lead.id)
    )).scalars().all()
    assert len(lead_files) == 1  # not 2


async def test_oversized_file_rejected_without_reading_full_content(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """Finding 4 (Important, task-6 review): an oversized file must be
    rejected using Starlette's `UploadFile.size` (populated during multipart
    body parsing, before this handler runs) BEFORE `.read()` is ever called
    on it — not after reading its full content into memory. Patches
    `UploadFile.read` to prove it is genuinely never invoked for this
    request, rather than merely asserting the eventual 422."""
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    from starlette.datastructures import UploadFile as StarletteUploadFile

    read_calls = 0
    original_read = StarletteUploadFile.read

    async def _counting_read(self: StarletteUploadFile, size: int = -1) -> bytes:
        nonlocal read_calls
        read_calls += 1
        return await original_read(self, size)

    with (
        patch("src.api.upload._MAX_FILE_SIZE_BYTES", 100),
        patch("src.api.upload.s3_put", new_callable=AsyncMock) as mock_put,
        patch.object(StarletteUploadFile, "read", _counting_read),
    ):
        resp = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[("files", ("big.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )

    assert resp.status_code == 422, resp.text
    mock_put.assert_not_called()
    # The handler's own size check must have rejected this file via `.size`
    # before ever calling `.read()` on it.
    assert read_calls == 0, (
        "handler called UploadFile.read() on an oversized file before "
        "rejecting it via .size — Finding 4 regression"
    )

    token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead.id)
    )).scalar_one()
    assert token_row.used_at is None


async def test_eleventh_request_within_an_hour_from_same_ip_returns_429(
    http_client: AsyncClient, hc_user: User, db: AsyncSession
):
    """SPEC-0001/PHASE-03 Decision D-3: 10 req/hour. The 11th POST from the same
    IP within an hour must 429. Reuses one token across all 11 requests — after
    the first successful upload it flips to "used", so requests 2-10 hit the
    "used" (200) branch rather than re-uploading; that's fine, the rate limiter
    counts every request regardless of what the handler does with it. Mirrors
    `test_intake_public.py`'s `test_sixth_submission_within_an_hour_...` pattern.
    """
    lead = await _make_lead(db, hc_user)
    raw_token = await _make_token(db, lead)
    await db.commit()

    with (
        patch("src.api.upload.s3_put", new_callable=AsyncMock),
        patch(
            "src.llm_service.generate_lead_brief", new_callable=AsyncMock,
            return_value=(None, None),
        ),
        patch("src.api.upload.send_lead_brief_failed_email"),
    ):
        for i in range(10):
            resp = await http_client.post(
                f"/api/upload/{raw_token}/files",
                files=[("files", (f"r{i}.pdf", _valid_pdf_with_text(), "application/pdf"))],
            )
            assert resp.status_code in (200, 201), f"request {i + 1} failed: {resp.text}"

        eleventh = await http_client.post(
            f"/api/upload/{raw_token}/files",
            files=[("files", ("r11.pdf", _valid_pdf_with_text(), "application/pdf"))],
        )
    assert eleventh.status_code == 429, eleventh.text
