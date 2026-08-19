"""add_client_messages_table

Revision ID: da409c0b55dc
Revises: b8cb150db2b2
Create Date: 2026-08-19 15:15:17.668991

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da409c0b55dc'
down_revision: Union[str, Sequence[str], None] = 'b8cb150db2b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "client_messages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hc_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("direction", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachment_storage_path", sa.Text, nullable=True),
        sa.Column("attachment_original_filename", sa.Text, nullable=True),
        sa.Column("attachment_mime_type", sa.Text, nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("direction IN ('client', 'coach')", name="ck_client_messages_direction"),
    )
    op.create_index("idx_client_messages_client_sent", "client_messages", ["client_id", "sent_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_client_messages_client_sent", table_name="client_messages")
    op.drop_table("client_messages")
