"""add_google_calendar_connections

Revision ID: c60540e93dfa
Revises: 97ef9da99879
Create Date: 2026-07-12 20:28:41.932710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c60540e93dfa'
down_revision: Union[str, Sequence[str], None] = '97ef9da99879'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "google_calendar_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("google_account_email", sa.Text(), nullable=False),
        sa.Column("scope_granted", sa.Text(), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("connected_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hc_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hc_user_id", name="uq_google_calendar_connections_hc_user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("google_calendar_connections")
