"""add_google_calendar_event_id_to_sessions

Revision ID: a2fa27bb126e
Revises: c60540e93dfa
Create Date: 2026-07-12 23:38:10.047673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2fa27bb126e'
down_revision: Union[str, Sequence[str], None] = 'c60540e93dfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sessions", sa.Column("google_calendar_event_id", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "google_calendar_event_id")
