"""Integration tests for GET /clients/{id}/ast. P5 Part A."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from src.db.models.coaching import ActionItem, CheckIn


@pytest.mark.asyncio
async def test_ast_empty_state_returns_correct_structure(http_client, hc_headers, client_rec):
    """Empty AST (no items, no check-ins) returns correct shape."""
    r = await http_client.get(f"/api/clients/{client_rec.id}/ast", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["open_items"] == []
    assert body["missed_items"] == []
    assert body["trend_tags"] == []
    assert isinstance(body["status_summary"], str)
    assert isinstance(body["triage_flags"], list)
    assert "no_recent_checkin" in body["triage_flags"]  # no check-ins = flag always present


@pytest.mark.asyncio
async def test_ast_open_items_appear(http_client, hc_headers, hc_user, client_rec, db):
    """Open action items appear in open_items list."""
    action = ActionItem(
        client_id=client_rec.id,
        hc_user_id=hc_user.id,
        description="Drink 2.5L water daily",
        status="open",
    )
    db.add(action)
    await db.flush()

    r = await http_client.get(f"/api/clients/{client_rec.id}/ast", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["open_items"]) == 1
    assert body["open_items"][0]["description"] == "Drink 2.5L water daily"
    assert body["open_items"][0]["status"] == "open"


@pytest.mark.asyncio
async def test_ast_missed_item_triggers_flag(http_client, hc_headers, hc_user, client_rec, db):
    """Missed action item → 'missed_action_item' in triage_flags."""
    action = ActionItem(
        client_id=client_rec.id,
        hc_user_id=hc_user.id,
        description="Walk 30 min",
        status="missed",
    )
    db.add(action)
    await db.flush()

    r = await http_client.get(f"/api/clients/{client_rec.id}/ast", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["missed_items"]) == 1
    assert "missed_action_item" in body["triage_flags"]


@pytest.mark.asyncio
async def test_ast_no_checkin_in_14_days_triggers_flag(http_client, hc_headers, hc_user, client_rec, db):
    """Zero check-ins in 14 days → 'no_recent_checkin' in triage_flags."""
    # Create a check-in that's 20 days old (outside 14-day window)
    old_checkin = CheckIn(
        client_id=client_rec.id,
        hc_user_id=hc_user.id,
        payload={"note": "Old check-in"},
        created_at=datetime.now(timezone.utc) - timedelta(days=20),
    )
    db.add(old_checkin)
    await db.flush()

    r = await http_client.get(f"/api/clients/{client_rec.id}/ast", headers=hc_headers)
    body = r.json()
    assert "no_recent_checkin" in body["triage_flags"]
    assert body["status_summary"] == "No recent check-ins."


@pytest.mark.asyncio
async def test_ast_cross_tenant_returns_404(http_client, hc2_headers, client_rec):
    """Different HC cannot access the AST → 404."""
    r = await http_client.get(f"/api/clients/{client_rec.id}/ast", headers=hc2_headers)
    assert r.status_code == 404
