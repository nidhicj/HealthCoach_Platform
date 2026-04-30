"""auth_refresh_tokens — per ADR-0005 §10."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import INET, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_token_hash", "token_hash"),
        Index(
            "idx_refresh_tokens_active",
            "user_id",
            postgresql_where="revoked_at IS NULL AND expires_at > NOW()",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    successor_id: Mapped[UUID | None] = mapped_column(ForeignKey("auth_refresh_tokens.id"))
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_at_issue: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
