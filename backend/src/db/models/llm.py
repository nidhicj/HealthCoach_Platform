"""llm_calls telemetry table. Per ADR-0003 §4 (amended 2026-05-04).

prompt_text and completion_text are stored as pgcrypto-encrypted BYTEA.
Never read these columns directly from the ORM — use tracking.fetch_llm_call() which
runs pgp_sym_decrypt() via raw SQL after SET LOCAL app.llm_call_encryption_key.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, LargeBinary, Numeric, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class LlmCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("idx_llm_calls_created_at", "created_at"),
        Index("idx_llm_calls_hc_use_case", "hc_user_id", "use_case"),
        Index(
            "idx_llm_calls_validation_failed",
            "validation_failed",
            postgresql_where="validation_failed = TRUE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("sessions.id"))
    request_id: Mapped[UUID | None] = mapped_column()
    use_case: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_requested: Mapped[str] = mapped_column(Text, nullable=False)
    model_served: Mapped[str | None] = mapped_column(Text)
    fallback_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    snippet_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    snippet_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    inr_cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    raw_request_id: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    # pgcrypto-encrypted; key injected via SET LOCAL before write/read
    prompt_text: Mapped[bytes | None] = mapped_column(LargeBinary)
    completion_text: Mapped[bytes | None] = mapped_column(LargeBinary)
