"""p11_client_demographics_and_health_metrics

P11 schema additions:
- clients: add demographics JSONB (nullable) — optional demographic info about the client
- clients: add health_metrics JSONB NOT NULL DEFAULT '[]' — HC-defined health metrics with current values

Revision ID: a1b2c3d4e5f6
Revises: df7c84b2de4f
Create Date: 2026-06-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "df7c84b2de4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("demographics", JSONB(), nullable=True))
    op.add_column(
        "clients",
        sa.Column("health_metrics", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("clients", "health_metrics")
    op.drop_column("clients", "demographics")
