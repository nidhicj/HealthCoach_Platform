"""Unit test: users.first_name / users.last_name columns exist, nullable, TEXT.

Temporary — conceptually owned by Unit_006_PlatformFoundations PHASE-01.
See Unit_003 PHASE-01 Global Constraints for the cross-branch coordination note.
"""
from sqlalchemy import Text

from src.db.models.users import User


def test_user_has_first_and_last_name_columns():
    cols = User.__table__.columns
    assert "first_name" in cols
    assert isinstance(cols["first_name"].type, Text)
    assert cols["first_name"].nullable is True
    assert "last_name" in cols
    assert isinstance(cols["last_name"].type, Text)
    assert cols["last_name"].nullable is True
