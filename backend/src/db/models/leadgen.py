"""Leadgen models: hc_leadgen_config. Per SPEC-0001-client-discovery-pipeline.md."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, func, text
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
