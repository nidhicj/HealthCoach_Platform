from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index("idx_clients_hc_user_id", "hc_user_id"),
        Index("idx_clients_journey_stage", "hc_user_id", "journey_stage"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(Text)
    journey_stage: Mapped[str] = mapped_column(Text, nullable=False, server_default="'onboarding'")
    course_start_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    course_end_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    course_goal: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
