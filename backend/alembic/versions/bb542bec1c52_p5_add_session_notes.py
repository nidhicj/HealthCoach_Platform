"""p5_add_session_notes

P5 schema addition:
- sessions: add session_notes TEXT (nullable) — coach-written notes captured
  during or after a session, distinct from notes_internal (private coach notes)
  and from LLM-generated recap. No backfill required; column is nullable from day one.

Revision ID: bb542bec1c52
Revises: 95df31e31f5f
Create Date: 2026-05-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bb542bec1c52"
down_revision: Union[str, Sequence[str], None] = "95df31e31f5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("session_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "session_notes")
