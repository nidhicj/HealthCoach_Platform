"""add_leads_core_tables

Revision ID: 5e8385088f08
Revises: 83e5cae9b85d
Create Date: 2026-08-02 14:39:45.037165

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5e8385088f08'
down_revision: Union[str, Sequence[str], None] = '83e5cae9b85d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create leads table
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("test_recommendation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("brief_text", sa.Text(), nullable=True),
        sa.Column("brief_llm_call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("llm_calls.id"), nullable=True),
        sa.Column("consent_given_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("consent_purpose", sa.Text(), nullable=True),
        sa.Column("converted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("converted_client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("hc_user_id", "email", name="uq_leads_hc_user_id_email"),
        sa.Index("idx_leads_hc_user_id", "hc_user_id"),
    )

    # Create lead_questionnaire_responses table
    op.create_table(
        "lead_questionnaire_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_key", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Index("idx_lead_qr_lead_id", "lead_id"),
    )

    # Create lead_upload_tokens table
    op.create_table(
        "lead_upload_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Index("idx_lead_upload_tokens_lead_id", "lead_id"),
    )

    # Create lead_files table
    op.create_table(
        "lead_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("purpose", sa.Text(), nullable=False, server_default=sa.text("'blood_report'")),
        sa.Index("idx_lead_files_lead_id", "lead_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("lead_files")
    op.drop_table("lead_upload_tokens")
    op.drop_table("lead_questionnaire_responses")
    op.drop_table("leads")
