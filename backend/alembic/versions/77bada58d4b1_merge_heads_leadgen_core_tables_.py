"""merge heads: leadgen core tables + platform-foundations chain

Revision ID: 77bada58d4b1
Revises: 5e8385088f08, b8cb150db2b2
Create Date: 2026-08-11 17:03:44.852512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77bada58d4b1'
down_revision: Union[str, Sequence[str], None] = ('5e8385088f08', 'b8cb150db2b2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
