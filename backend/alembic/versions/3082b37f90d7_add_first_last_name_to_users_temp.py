"""add_first_last_name_to_users_temp

Revision ID: 3082b37f90d7
Revises: 97ef9da99879
Create Date: 2026-08-02 14:25:21.420066

HISTORICAL NOTE (updated 2026-08-21): these columns were originally added here,
by Unit_003, as a stated TEMPORARY measure to unblock leadgen setup ahead of
Unit_006_PlatformFoundations's real settings/profile work — see the original
warning this replaces, and PHASE-01's Global Constraints section
(docs/specs/Unit_003_ClientDiscoveryPipeline/PHASE-01-leadgen-data-layer-and-setup.md)
for that history.

That risk did not materialize. `Unit_006_PlatformFoundations` PHASE-01 took
ownership of `users.first_name`/`users.last_name` on 2026-08-21 via its own
Task 4, reusing this migration rather than adding a second one for the same
columns — so the duplicate-column merge conflict warned about below never
occurred. The seed script this migration's data once depended on
(`backend/scripts/seed_hc_names.py`) was deleted in that same Unit_006 batch
(Task 6); it no longer exists and does not need rebasing. This migration is
otherwise permanent — do not drop it. See `SPEC-0001-client-discovery-pipeline.md`
§Open questions and `Unit_006_PlatformFoundations/PHASE-01-hc-settings-profile.md`
§"Post-phase extension — 2026-08-21" for the resolution record.
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
