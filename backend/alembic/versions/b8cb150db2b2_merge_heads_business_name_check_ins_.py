"""merge heads: business_name + check_ins.requested_at

Revision ID: b8cb150db2b2
Revises: 6503e78ca409, f6e082127ba8
Create Date: 2026-08-05 12:03:04.022868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8cb150db2b2'
down_revision: Union[str, Sequence[str], None] = ('6503e78ca409', 'f6e082127ba8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
