"""Leadgen models: hc_leadgen_config. Per SPEC-0001-client-discovery-pipeline.md."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class HcLeadgenConfig(Base):
    """One row per HC. hc_slug is immutable after creation — no update path exists."""
    __tablename__ = "hc_leadgen_config"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    hc_slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    questionnaire: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    test_panel: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        default=lambda: {"standard_tests": [], "condition_rules": []},
        server_default=text("'{\"standard_tests\": [], \"condition_rules\": []}'::jsonb"),
    )
    consultation_fee_inr: Mapped[int | None] = mapped_column()
    consultation_duration_min: Mapped[int] = mapped_column(nullable=False, default=45, server_default=text("45"))
    scheduling_link: Mapped[str | None] = mapped_column(Text)
    notification_delivery: Mapped[str] = mapped_column(Text, nullable=False, default="email", server_default=text("'email'"))
    lead_expiry_days: Mapped[int] = mapped_column(nullable=False, default=60, server_default=text("60"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("hc_user_id", "email", name="uq_leads_hc_user_id_email"),
        Index("idx_leads_hc_user_id", "hc_user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    draft_test_recommendation: Mapped[dict | None] = mapped_column(JSONB)
    test_recommendation: Mapped[dict | None] = mapped_column(JSONB)
    payment_status: Mapped[str] = mapped_column(Text, nullable=False, default="unpaid", server_default=text("'unpaid'"))
    payment_reference: Mapped[str | None] = mapped_column(Text)
    paid_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    scheduled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    meeting_link: Mapped[str | None] = mapped_column(Text)
    brief_text: Mapped[str | None] = mapped_column(Text)
    brief_llm_call_id: Mapped[UUID | None] = mapped_column(ForeignKey("llm_calls.id"))
    consent_given_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    consent_purpose: Mapped[str | None] = mapped_column(Text)
    converted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    converted_client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id"))
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class LeadQuestionnaireResponse(Base):
    __tablename__ = "lead_questionnaire_responses"
    __table_args__ = (Index("idx_lead_qr_lead_id", "lead_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    question_key: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class LeadUploadToken(Base):
    __tablename__ = "lead_upload_tokens"
    __table_args__ = (Index("idx_lead_upload_tokens_lead_id", "lead_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Nullable per SPEC-0001 D-8 (PHASE-05 Task 3): the row is now minted at
    # Stage 3 Send-time, before payment. NULL until leads.payment_status
    # flips to paid (Task 6 gate). See
    # alembic/versions/c6fcc8bae2f1_lead_upload_tokens_expires_at_nullable.py
    # for the full reasoning, including why the downgrade is one-way once
    # real NULLs exist.
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class LeadFile(Base):
    __tablename__ = "lead_files"
    __table_args__ = (Index("idx_lead_files_lead_id", "lead_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="blood_report", server_default=text("'blood_report'"))
