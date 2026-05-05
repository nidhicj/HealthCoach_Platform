"""p5b_add_client_files

P5 Part B schema addition:
- client_files: new table for per-session uploaded files (Zoom summaries, transcripts,
  attachments). Pluggable transcript-source design (arch principle §9.2).

Revision ID: df7c84b2de4f
Revises: bb542bec1c52
Create Date: 2026-05-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "df7c84b2de4f"
down_revision: Union[str, Sequence[str], None] = "bb542bec1c52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_zoom_summary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hc_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_client_files_session", "client_files", ["session_id"])
    op.create_index("idx_client_files_hc", "client_files", ["hc_user_id"])
    op.create_index("idx_client_files_client", "client_files", ["client_id"])


def downgrade() -> None:
    op.drop_index("idx_client_files_client", "client_files")
    op.drop_index("idx_client_files_hc", "client_files")
    op.drop_index("idx_client_files_session", "client_files")
    op.drop_table("client_files")
