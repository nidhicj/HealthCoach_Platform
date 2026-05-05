"""ClientFile ORM model — per-session uploaded files. P5 Part B."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class ClientFile(Base):
    __tablename__ = "client_files"
    __table_args__ = (
        Index("idx_client_files_session", "session_id"),
        Index("idx_client_files_hc", "hc_user_id"),
        Index("idx_client_files_client", "client_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_zoom_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
