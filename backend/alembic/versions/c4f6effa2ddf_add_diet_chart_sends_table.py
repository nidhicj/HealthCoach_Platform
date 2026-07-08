"""add_diet_chart_sends_table

Revision ID: c4f6effa2ddf
Revises: 9d5f26237132
Create Date: 2026-07-08 16:39:09.612186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f6effa2ddf'
down_revision: Union[str, Sequence[str], None] = '9d5f26237132'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diet_chart_sends",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", sa.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hc_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chart_name", sa.Text(), nullable=False),
        sa.Column("chart_parameters", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_diet_chart_sends_client_sent", "diet_chart_sends", ["client_id", "sent_at"])


def downgrade() -> None:
    op.drop_index("idx_diet_chart_sends_client_sent", table_name="diet_chart_sends")
    op.drop_table("diet_chart_sends")
