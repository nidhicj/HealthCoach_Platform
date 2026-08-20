"""add_hc_leadgen_config_table

Revision ID: 83e5cae9b85d
Revises: 3082b37f90d7
Create Date: 2026-08-02 14:30:02.487693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '83e5cae9b85d'
down_revision: Union[str, Sequence[str], None] = '3082b37f90d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hc_leadgen_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("hc_slug", sa.Text(), nullable=False, unique=True),
        sa.Column("questionnaire", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("test_panel", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                   server_default=sa.text('\'{"standard_tests": [], "condition_rules": []}\'::jsonb')),
        sa.Column("consultation_fee_inr", sa.Integer(), nullable=True),
        sa.Column("consultation_duration_min", sa.Integer(), nullable=False, server_default=sa.text("45")),
        sa.Column("scheduling_link", sa.Text(), nullable=True),
        sa.Column("notification_delivery", sa.Text(), nullable=False, server_default=sa.text("'email'")),
        sa.Column("lead_expiry_days", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("hc_leadgen_config")
