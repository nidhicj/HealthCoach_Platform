"""add_first_last_name_to_users_temp

Revision ID: 3082b37f90d7
Revises: 97ef9da99879
Create Date: 2026-08-02 14:25:21.420066

TEMPORARY. These columns are conceptually owned by Unit_006_PlatformFoundations,
not Unit_003 — added here only to unblock leadgen setup ahead of Unit_006's real
settings/profile work. If feature/unit-006-platform-foundations adds its own
migration for users.first_name/last_name before this branch merges, whichever
merges second will hit a duplicate-column conflict. See PHASE-01's Global
Constraints section (docs/specs/Unit_003_ClientDiscoveryPipeline/
PHASE-01-leadgen-data-layer-and-setup.md) for the full coordination note — this
migration may need to be dropped and the seed data rebased once Unit_006 lands.
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
