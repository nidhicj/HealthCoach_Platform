"""add_google_calendar_event_title_to_sessions

Revision ID: c8af0b7b55f9
Revises: a2fa27bb126e
Create Date: 2026-07-13 12:31:25.594618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8af0b7b55f9'
down_revision: Union[str, Sequence[str], None] = 'a2fa27bb126e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sessions", sa.Column("google_calendar_event_title", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "google_calendar_event_title")
