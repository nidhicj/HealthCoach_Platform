"""Integration tests: `leads` payment/scheduling columns +
`lead_upload_tokens.expires_at` nullability. PHASE-05 Task 3 — schema/model
only, no endpoint or business logic reads/writes these yet (Tasks 4-6 of this
phase own that)."""
import hashlib
import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Lead, LeadUploadToken, User

pytestmark = pytest.mark.asyncio


async def test_lead_payment_scheduling_columns_default_on_insert(
    db: AsyncSession, hc_user: User
) -> None:
    """`payment_status` defaults to 'unpaid' via the column's server_default;
    the other four new columns (payment_reference, paid_at, scheduled_at,
    meeting_link) default to NULL when not supplied at insert time — per
    SPEC-0001's §Data section for `leads`."""
    lead = Lead(
        hc_user_id=hc_user.id,
        full_name="Payment Column Test",
        email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
        status="tests_recommended",
    )
    db.add(lead)
    await db.flush()

    assert lead.payment_status == "unpaid"
    assert lead.payment_reference is None
    assert lead.paid_at is None
    assert lead.scheduled_at is None
    assert lead.meeting_link is None


async def test_lead_upload_token_accepts_expires_at_none(
    db: AsyncSession, hc_user: User
) -> None:
    """SPEC-0001 D-8: `lead_upload_tokens` is now minted at Stage 3 Send-time,
    before payment — `expires_at` must be insertable as NULL. (The gating
    behavior that reads a NULL `expires_at` is Task 6's job, not this one;
    this test only confirms the schema/type allows it.)"""
    lead = Lead(
        hc_user_id=hc_user.id,
        full_name="Upload Token Nullable Test",
        email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
        status="tests_recommended",
    )
    db.add(lead)
    await db.flush()

    token = LeadUploadToken(
        lead_id=lead.id,
        token_hash=hashlib.sha256(os.urandom(32)).hexdigest(),
        expires_at=None,
    )
    db.add(token)
    await db.flush()

    assert token.expires_at is None
