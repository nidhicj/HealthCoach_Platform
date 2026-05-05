"""p4_llm_service_schema

P4 LLM Service schema additions:
- llm_calls: add prompt_text BYTEA and completion_text BYTEA (pgcrypto-encrypted)
- llm_calls: fix client_id FK to ON DELETE CASCADE (consent revocation cascade)
- clients: add code TEXT (per-HC pseudonym CP0001…) with per-HC unique constraint
- pgcrypto: ensure extension exists

Revision ID: 95df31e31f5f
Revises: 60775f9338d3
Create Date: 2026-05-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "95df31e31f5f"
down_revision: Union[str, Sequence[str], None] = "60775f9338d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_llm_calls_client_id_p4"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- llm_calls: encrypted content columns ---
    op.add_column("llm_calls", sa.Column("prompt_text", sa.LargeBinary(), nullable=True))
    op.add_column("llm_calls", sa.Column("completion_text", sa.LargeBinary(), nullable=True))

    # --- llm_calls: fix client_id FK to cascade on client delete ---
    op.drop_constraint("llm_calls_client_id_fkey", "llm_calls", type_="foreignkey")
    op.create_foreign_key(FK_NAME, "llm_calls", "clients", ["client_id"], ["id"], ondelete="CASCADE")

    # --- clients: add code column, backfill, unique constraint ---
    op.add_column("clients", sa.Column("code", sa.Text(), nullable=True))
    # Backfill: assign CP0001, CP0002, ... per HC, ordered by created_at
    op.execute("""
        WITH ranked AS (
            SELECT id, hc_user_id,
                   ROW_NUMBER() OVER (PARTITION BY hc_user_id ORDER BY created_at) AS rn
            FROM clients
        )
        UPDATE clients c
        SET code = 'CP' || LPAD(r.rn::text, 4, '0')
        FROM ranked r
        WHERE c.id = r.id
    """)
    op.alter_column("clients", "code", nullable=False)
    op.create_unique_constraint("uq_clients_hc_user_id_code", "clients", ["hc_user_id", "code"])


def downgrade() -> None:
    op.drop_constraint("uq_clients_hc_user_id_code", "clients", type_="unique")
    op.drop_column("clients", "code")
    op.drop_constraint(FK_NAME, "llm_calls", type_="foreignkey")
    op.create_foreign_key("llm_calls_client_id_fkey", "llm_calls", "clients", ["client_id"], ["id"])
    op.drop_column("llm_calls", "completion_text")
    op.drop_column("llm_calls", "prompt_text")
