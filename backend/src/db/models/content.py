"""diet_charts, prep_recipes, diet_chart_recipes, content_assignments."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, PrimaryKeyConstraint, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class DietChart(Base):
    __tablename__ = "diet_charts"
    __table_args__ = (
        Index("idx_diet_charts_hc_user_id", "hc_user_id", postgresql_where="archived_at IS NULL"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class PrepRecipe(Base):
    __tablename__ = "prep_recipes"
    __table_args__ = (
        Index("idx_prep_recipes_hc_user_id", "hc_user_id", postgresql_where="archived_at IS NULL"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    ingredients: Mapped[dict] = mapped_column(JSONB, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class DietChartRecipe(Base):
    """Many-to-many join between diet_charts and prep_recipes."""
    __tablename__ = "diet_chart_recipes"
    __table_args__ = (
        PrimaryKeyConstraint("diet_chart_id", "prep_recipe_id"),
    )

    diet_chart_id: Mapped[UUID] = mapped_column(ForeignKey("diet_charts.id", ondelete="CASCADE"))
    prep_recipe_id: Mapped[UUID] = mapped_column(ForeignKey("prep_recipes.id", ondelete="CASCADE"))


class ContentAssignment(Base):
    __tablename__ = "content_assignments"
    __table_args__ = (
        Index("idx_content_assignments_client", "client_id", "assigned_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("sessions.id"))
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_id: Mapped[UUID] = mapped_column(nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)
