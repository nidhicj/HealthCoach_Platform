"""moms, briefs, action_items, check_ins — the core coaching cycle tables."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import ARRAY, Date, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Mom(Base):
    """Minutes of Meeting — one per session."""
    __tablename__ = "moms"
    __table_args__ = (
        Index("idx_moms_status", "status"),
        Index("idx_moms_client_id", "client_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    final_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="'draft'")
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    sent_to_email: Mapped[str | None] = mapped_column(Text)
    llm_call_id: Mapped[UUID | None] = mapped_column(ForeignKey("llm_calls.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class Brief(Base):
    """Pre-session brief — one per session, internal only."""
    __tablename__ = "briefs"
    __table_args__ = (Index("idx_briefs_session_id", "session_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    brief_text: Mapped[str] = mapped_column(Text, nullable=False)
    triage_flags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    llm_call_id: Mapped[UUID | None] = mapped_column(ForeignKey("llm_calls.id"))
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class ActionItem(Base):
    __tablename__ = "action_items"
    __table_args__ = (Index("idx_action_items_client_status", "client_id", "status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="'open'")
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class CheckIn(Base):
    __tablename__ = "check_ins"
    __table_args__ = (Index("idx_check_ins_client_created", "client_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sentiment_flag: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class HcStyleSnippet(Base):
    __tablename__ = "hc_style_snippets"
    __table_args__ = (
        Index("idx_snippets_hc_user_id", "hc_user_id"),
        Index("idx_snippets_client_id", "client_id"),
        Index("idx_snippets_last_used", "hc_user_id", "last_used_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    snippet_type: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    hc_modified_text: Mapped[str | None] = mapped_column(Text)
    context_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    relevance_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
