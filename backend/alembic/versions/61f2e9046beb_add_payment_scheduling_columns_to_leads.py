"""add_payment_scheduling_columns_to_leads

Revision ID: 61f2e9046beb
Revises: 1507b5062974
Create Date: 2026-08-25 11:40:17.642210

PHASE-05 (payment + scheduling handoff), Task 3. Five new columns on `leads`,
copied verbatim from SPEC-0001-client-discovery-pipeline.md's §Data section
(the `leads` table row-list, `payment_status` through `meeting_link`):

  payment_status     TEXT NOT NULL DEFAULT 'unpaid'  -- enum: unpaid/paid/failed/refunded
  payment_reference  TEXT           -- Razorpay order/payment ID; null until a payment attempt exists
  paid_at            TIMESTAMPTZ    -- null unless payment_status = paid
  scheduled_at       TIMESTAMPTZ    -- confirmed consultation appointment time; null until scheduling handoff completes
  meeting_link       TEXT           -- null until scheduling handoff completes

No business logic reads/writes these yet (Tasks 4-6 of this phase); this
migration is schema-only.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '61f2e9046beb'
down_revision: str | Sequence[str] | None = '1507b5062974'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("leads", sa.Column("payment_status", sa.Text(), nullable=False, server_default=sa.text("'unpaid'")))
    op.add_column("leads", sa.Column("payment_reference", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("paid_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("scheduled_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("meeting_link", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    Plain drop_column x5. This is the ordinary, expected shape of an
    add-column downgrade — any values written into these columns after
    upgrade (real payment/scheduling data) are lost, same as `leads` rows
    that predate this migration entirely losing nothing they never had.
    Unlike the next migration in this chain
    (`c6fcc8bae2f1_lead_upload_tokens_expires_at_nullable.py`), there is no
    NOT-NULL-re-add hazard here: downgrade only removes columns, it never
    tightens a constraint against data that might not satisfy it.
    """
    op.drop_column("leads", "meeting_link")
    op.drop_column("leads", "scheduled_at")
    op.drop_column("leads", "paid_at")
    op.drop_column("leads", "payment_reference")
    op.drop_column("leads", "payment_status")
