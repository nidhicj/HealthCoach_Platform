"""add_business_name_to_users

Revision ID: 6503e78ca409
Revises: 97ef9da99879
Create Date: 2026-08-03 17:03:00.549089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6503e78ca409'
down_revision: Union[str, Sequence[str], None] = '97ef9da99879'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("business_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "business_name")
