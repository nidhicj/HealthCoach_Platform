"""add_requested_at_to_check_ins

Revision ID: f6e082127ba8
Revises: c8af0b7b55f9
Create Date: 2026-07-21 16:35:02.453523

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6e082127ba8'
down_revision: Union[str, Sequence[str], None] = 'c8af0b7b55f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("check_ins", sa.Column("requested_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.alter_column("check_ins", "payload", existing_type=sa.dialects.postgresql.JSONB, nullable=True)


def downgrade() -> None:
    op.alter_column("check_ins", "payload", existing_type=sa.dialects.postgresql.JSONB, nullable=False)
    op.drop_column("check_ins", "requested_at")
