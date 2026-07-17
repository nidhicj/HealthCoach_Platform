"""Unit test: Mom.action_items_draft column exists and round-trips a JSON list."""
import pytest
import sqlalchemy as sa

from src.db.models.coaching import Mom


def test_mom_has_action_items_draft_column():
    assert "action_items_draft" in Mom.__table__.columns
    col = Mom.__table__.columns["action_items_draft"]
    assert isinstance(col.type, sa.dialects.postgresql.JSONB)
    assert col.nullable is True
