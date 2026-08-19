"""add_meal_logs_table

Revision ID: 759ce327038e
Revises: da409c0b55dc
Create Date: 2026-08-19 17:54:04.784287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '759ce327038e'
down_revision: Union[str, Sequence[str], None] = 'da409c0b55dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hc_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("meal_slot", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("photo_storage_path", sa.Text, nullable=False),
        sa.Column("photo_original_filename", sa.Text, nullable=False),
        sa.Column("photo_mime_type", sa.Text, nullable=False),
        sa.Column("captured_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("logged_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("hc_reaction", sa.Text, nullable=True),
        sa.Column("reacted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "meal_slot IN ('breakfast', 'morning_snack', 'lunch', 'evening_snack', 'dinner')",
            name="ck_meal_logs_meal_slot",
        ),
        sa.CheckConstraint(
            "hc_reaction IN ('happy', 'neutral', 'sad') OR hc_reaction IS NULL",
            name="ck_meal_logs_hc_reaction",
        ),
    )
    op.create_index("idx_meal_logs_client_logged", "meal_logs", ["client_id", "logged_at"])


def downgrade() -> None:
    op.drop_index("idx_meal_logs_client_logged", table_name="meal_logs")
    op.drop_table("meal_logs")
