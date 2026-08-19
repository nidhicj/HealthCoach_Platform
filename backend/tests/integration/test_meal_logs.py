"""HC-side meal_logs list/react endpoints (PHASE-03 Task 5).

NOTE on test-helper adaptation: the plan's own brief describes a `_log_meal`
helper that POSTs to `/api/me/meal-logs` (Task 4's client-side submit
endpoint). Task 4 is implemented AFTER this task (per controller ruling —
Task 4 imports MealLogOut/ALLOWED_MEAL_PHOTO_MIME_TYPES/
MAX_MEAL_PHOTO_SIZE_BYTES from this module, so it cannot land first), so
that endpoint does not exist yet here. `_make_meal_log` below inserts a
MealLog row directly via the ORM instead, matching the direct-insert
pattern already used for fixture setup in test_models.py's cascade-delete
tests. When Task 4 lands, its own tests will exercise the real HTTP
endpoint.
"""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Client, MealLog, User


async def _make_client(http_client, headers) -> dict:
    r = await http_client.post("/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 201
    return r.json()


async def _make_meal_log(
    db: AsyncSession, client: Client, hc: User, meal_slot: str = "breakfast", **overrides
) -> MealLog:
    meal_log = MealLog(
        client_id=client.id,
        hc_user_id=hc.id,
        meal_slot=meal_slot,
        description=overrides.get("description", "test meal"),
        photo_storage_path=overrides.get("photo_storage_path", "client-x/meal-logs/y/z.jpg"),
        photo_original_filename=overrides.get("photo_original_filename", "z.jpg"),
        photo_mime_type=overrides.get("photo_mime_type", "image/jpeg"),
    )
    db.add(meal_log)
    await db.flush()
    await db.commit()
    return meal_log


@pytest.mark.asyncio
async def test_hc_lists_client_meal_logs(db, http_client, hc_headers, client_rec, hc_user):
    await _make_meal_log(db, client_rec, hc_user)
    r = await http_client.get(f"/api/clients/{client_rec.id}/meal-logs", headers=hc_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_meal_logs_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/meal-logs", headers=hc2_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_hc_can_react_to_a_meal_log(db, http_client, hc_headers, client_rec, hc_user):
    meal = await _make_meal_log(db, client_rec, hc_user)
    r = await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal.id}/react",
        headers=hc_headers, json={"reaction": "happy"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["hc_reaction"] == "happy"
    assert r.json()["reacted_at"] is not None


@pytest.mark.asyncio
async def test_hc_can_change_reaction(db, http_client, hc_headers, client_rec, hc_user):
    meal = await _make_meal_log(db, client_rec, hc_user)
    await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal.id}/react",
        headers=hc_headers, json={"reaction": "sad"},
    )
    r2 = await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal.id}/react",
        headers=hc_headers, json={"reaction": "happy"},
    )
    assert r2.json()["hc_reaction"] == "happy"  # overwritable — Design Decision 2


@pytest.mark.asyncio
async def test_react_rejects_invalid_value(db, http_client, hc_headers, client_rec, hc_user):
    meal = await _make_meal_log(db, client_rec, hc_user)
    r = await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal.id}/react",
        headers=hc_headers, json={"reaction": "angry"},
    )
    assert r.status_code == 422
