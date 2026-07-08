"""Unit test: DietChartSend model exists with the right columns and types."""
import sqlalchemy as sa

from src.db.models.content import DietChartSend


def test_diet_chart_send_has_expected_columns():
    cols = DietChartSend.__table__.columns
    assert "id" in cols
    assert "client_id" in cols
    assert "hc_user_id" in cols
    assert "chart_name" in cols
    assert "chart_parameters" in cols
    assert isinstance(cols["chart_parameters"].type, sa.dialects.postgresql.JSONB)
    assert "sent_at" in cols
    assert cols["client_id"].nullable is False
    assert cols["hc_user_id"].nullable is False
    assert cols["chart_name"].nullable is False
    assert cols["chart_parameters"].nullable is False
