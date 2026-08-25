"""add_draft_test_recommendation_to_leads

Revision ID: 1f2a6c9d4e17
Revises: 77bada58d4b1
Create Date: 2026-08-24 00:00:00.000000

PHASE-04 (AI-drafted test recommendation + HC review/send) needs a place to
store the AI's first-draft panel separately from `leads.test_recommendation`
(which becomes the finalized, HC-approved, Lead-facing version only once the
HC clicks Send — SPEC-0001 §Stage 3, §Data). Same JSONB shape as
`test_recommendation`: `{standard, additions, all_tests}`. Nullable — null
until Stage 3's LLM call completes (or, per this phase's Task 3, until the
endpoint writes the standard-baseline-only fallback shape on AI-drafting
failure).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1f2a6c9d4e17'
down_revision: Union[str, Sequence[str], None] = '77bada58d4b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "leads",
        sa.Column("draft_test_recommendation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("leads", "draft_test_recommendation")
