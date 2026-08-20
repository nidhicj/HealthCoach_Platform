"""merge_heads_meal_logs_and_leadgen

Revision ID: 31d0ae6dcac6
Revises: 759ce327038e, 77bada58d4b1
Create Date: 2026-08-20 13:22:15.843589

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31d0ae6dcac6'
down_revision: Union[str, Sequence[str], None] = ('759ce327038e', '77bada58d4b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
