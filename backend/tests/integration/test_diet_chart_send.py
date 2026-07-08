"""Integration tests for POST /clients/{id}/diet-chart/send — snapshot creation (D-16)."""
import pytest
import sqlalchemy as sa

from src.db.models.content import DietChartSend


@pytest.mark.asyncio
async def test_send_creates_snapshot_from_active_chart(http_client, hc_headers, db, client_rec):
    """Sending copies the client's current active chart into a permanent snapshot row."""
    template_r = await http_client.post(
        "/api/diet-charts/templates/paste",
        headers=hc_headers,
        json={"name": "Basic Plan", "text": "Day\tBreakfast\nMonday\tOats"},
    )
    assert template_r.status_code == 201, template_r.text
    template_id = template_r.json()["id"]

    gen_r = await http_client.post(
        f"/api/clients/{client_rec.id}/diet-chart/generate",
        headers=hc_headers,
        json={"template_id": template_id},
    )
    assert gen_r.status_code == 200, gen_r.text
    chart = gen_r.json()["chart"]

    send_r = await http_client.post(
        f"/api/clients/{client_rec.id}/diet-chart/send",
        headers=hc_headers,
    )
    assert send_r.status_code == 201, send_r.text
    body = send_r.json()
    assert body["client_id"] == str(client_rec.id)
    assert body["chart_name"] == chart["name"]
    assert body["sent_at"] is not None

    rows = (await db.execute(
        sa.select(DietChartSend).where(DietChartSend.client_id == client_rec.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].chart_parameters == chart["parameters"]


@pytest.mark.asyncio
async def test_send_twice_creates_two_independent_snapshots(http_client, hc_headers, db, client_rec):
    """Each send is its own permanent record — sending twice does not overwrite the first."""
    template_r = await http_client.post(
        "/api/diet-charts/templates/paste",
        headers=hc_headers,
        json={"name": "Basic Plan", "text": "Day\tBreakfast\nMonday\tOats"},
    )
    template_id = template_r.json()["id"]
    await http_client.post(
        f"/api/clients/{client_rec.id}/diet-chart/generate",
        headers=hc_headers,
        json={"template_id": template_id},
    )

    first = await http_client.post(f"/api/clients/{client_rec.id}/diet-chart/send", headers=hc_headers)
    assert first.status_code == 201

    # HC edits the working chart between sends
    patch_r = await http_client.patch(
        f"/api/clients/{client_rec.id}/diet-chart",
        headers=hc_headers,
        json={"parameters": {"meal_slots": ["Breakfast"], "grid": {"Monday": {"Breakfast": {"food": "Poha", "timing": "8am"}}}}},
    )
    assert patch_r.status_code == 200

    second = await http_client.post(f"/api/clients/{client_rec.id}/diet-chart/send", headers=hc_headers)
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]

    rows = (await db.execute(
        sa.select(DietChartSend).where(DietChartSend.client_id == client_rec.id)
    )).scalars().all()
    assert len(rows) == 2
    parameters_by_send = {str(r.id): r.chart_parameters for r in rows}
    assert parameters_by_send[first.json()["id"]] != parameters_by_send[second.json()["id"]]


@pytest.mark.asyncio
async def test_send_returns_404_when_no_active_chart(http_client, hc_headers, client_rec):
    """Sending before any chart has been generated for this client returns a clean 404."""
    r = await http_client.post(f"/api/clients/{client_rec.id}/diet-chart/send", headers=hc_headers)
    assert r.status_code == 404
