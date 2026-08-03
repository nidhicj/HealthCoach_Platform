"""Unit test: users.business_name column exists, nullable, correct type."""
from sqlalchemy import Text

from src.db.models.users import User


def test_user_has_business_name_column():
    cols = User.__table__.columns
    assert "business_name" in cols
    assert isinstance(cols["business_name"].type, Text)
    assert cols["business_name"].nullable is True
