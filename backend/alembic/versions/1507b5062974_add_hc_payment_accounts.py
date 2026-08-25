"""add_hc_payment_accounts

Revision ID: 1507b5062974
Revises: 1f2a6c9d4e17
Create Date: 2026-08-25 11:08:53.146490

PHASE-05 (payment + scheduling handoff), Task 1. New table `hc_payment_accounts`:
one row per HC, holding their own Razorpay `key_id`/`key_secret`/`webhook_secret`
(Fernet-encrypted via EncryptedJSON(settings_key="razorpay_credentials_encryption_key"),
mirroring google_calendar_connections' credentials column). `credentials` and
`connected_at` are both nullable — a row can exist before a verified key pair is on
file (see src/db/models/payments.py docstring). Foundational migration only; no
later-task tables (payment_orders / webhook log, etc.) are touched here.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1507b5062974'
down_revision: str | Sequence[str] | None = '1f2a6c9d4e17'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "hc_payment_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=True),
        sa.Column("connected_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hc_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hc_user_id", name="uq_hc_payment_accounts_hc_user_id"),
    )


def downgrade() -> None:
    """Downgrade schema.

    Plain drop_table: this table has not shipped to any environment yet (Task 1 of a
    fresh phase), so there is no real data-loss risk to guard against on downgrade —
    unlike a later migration that drops a column already holding production data.
    """
    op.drop_table("hc_payment_accounts")
