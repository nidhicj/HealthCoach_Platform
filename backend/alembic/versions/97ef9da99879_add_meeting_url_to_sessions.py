"""add_meeting_url_to_sessions

Revision ID: 97ef9da99879
Revises: c4f6effa2ddf
Create Date: 2026-07-09 15:45:24.114087

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97ef9da99879'
down_revision: Union[str, Sequence[str], None] = 'c4f6effa2ddf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sessions", sa.Column("meeting_url", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "meeting_url")
