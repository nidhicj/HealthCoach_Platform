"""Integration tests: GET /api/upload/:token (public, unauthenticated). PHASE-03
Task 5. No POST endpoint exists in src.api.upload yet — that's Task 6."""
import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Lead, LeadUploadToken, User

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
