"""Unit test: HcLeadgenConfig model — columns, types, defaults."""
import sqlalchemy as sa

from src.db.models.leadgen import HcLeadgenConfig


def test_hc_leadgen_config_columns():
    cols = HcLeadgenConfig.__table__.columns
    assert cols["hc_user_id"].nullable is False
    assert cols["hc_slug"].nullable is False
    assert cols["hc_slug"].unique is True
    assert isinstance(cols["questionnaire"].type, sa.dialects.postgresql.JSONB)
    assert isinstance(cols["test_panel"].type, sa.dialects.postgresql.JSONB)
    assert cols["consultation_duration_min"].nullable is False
    assert cols["lead_expiry_days"].nullable is False
