"""add_first_last_name_to_users_temp

Revision ID: 3082b37f90d7
Revises: 97ef9da99879
Create Date: 2026-08-02 14:25:21.420066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3082b37f90d7'
down_revision: Union[str, Sequence[str], None] = '97ef9da99879'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("first_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
