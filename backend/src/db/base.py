"""SQLAlchemy 2.0 declarative base. Import Base here; never from individual model files."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
