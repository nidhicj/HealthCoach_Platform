"""lead_upload_tokens_expires_at_nullable

Revision ID: c6fcc8bae2f1
Revises: 61f2e9046beb
Create Date: 2026-08-25 11:40:20.199633

PHASE-05 (payment + scheduling handoff), Task 3. Per SPEC-0001 D-8: the
`lead_upload_tokens` row is now minted at Stage 3 Send-time (moved out of
Stage 4, where it originally sat) — *before* the Lead has paid. Its
`expires_at` clock is deliberately not started until `leads.payment_status`
flips to `paid` (so a Lead who takes 10 days to book still gets the full
14-day upload window, not a shortened one). That means `expires_at` must be
able to hold NULL between issuance and payment success — a state that, for
any Lead who never completes payment, persists indefinitely by design, not
just transiently.

Upgrade: DROP NOT NULL only. Loosening a constraint is always safe against
existing NOT-NULL data — every current row keeps its non-null value.

Downgrade: see the docstring on `downgrade()` below — this is a real decision,
not a formality.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c6fcc8bae2f1'
down_revision: str | Sequence[str] | None = '61f2e9046beb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "lead_upload_tokens", "expires_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema.

    ONE-WAY IN PRACTICE once real Leads have flowed through Stage 3 (SPEC-0001
    D-8), by deliberate choice — read this before touching it.

    `expires_at` is NULL by design for the entire window between token
    issuance (Stage 3 Send-time) and payment success. For any Lead who is
    sent their booking/upload email but never completes payment, that NULL
    is not transitional migration-window data waiting to be cleaned up — it
    is the correct, expected, permanent state of that row. A non-trivial
    fraction of `lead_upload_tokens` rows in a live environment can be
    expected to look like this at any given time.

    Two ways to re-add NOT NULL were considered:

    1. Backfill a sentinel timestamp into every NULL row, then re-add the
       constraint. REJECTED. `_resolve_token()` (`src/api/upload.py`) treats
       `expires_at` as "the" signal via `expires_at < now()`: a sentinel in
       the past makes an unpaid Lead's still-valid token look "expired"
       (wrong copy: "link expired" instead of "complete your booking
       first"); a sentinel in the future makes it look "valid" and bypasses
       the payment gate entirely (Task 6's whole point). There is no
       sentinel value that doesn't actively misrepresent payment-gate state
       for real rows — this is worse than refusing to downgrade, because it
       fails silently at the *application* layer instead of loudly at the
       *migration* layer.

    2. Document this as one-way in practice and refuse explicitly if any row
       currently violates the constraint being re-added, rather than either
       (a) silently attempting `ALTER COLUMN ... SET NOT NULL` and letting a
       bare Postgres `NotNullViolation` be the only signal (technically loud,
       but unhelpful — it doesn't explain *why* NULLs are expected here or
       what to do about them), or (b) silently succeeding in a way that
       quietly breaks the payment gate for existing rows. CHOSEN.

    Concretely: this downgrade counts NULL `expires_at` rows first and raises
    a clear, actionable `RuntimeError` if any exist, instead of proceeding to
    `alter_column`. If (and only if) no row currently has a NULL
    `expires_at` — e.g. downgrading immediately after upgrading, before any
    Task 4+ code has ever written a NULL — the downgrade proceeds normally.
    Recovering from the blocked case is a real business decision (e.g.
    deciding what should happen to those Leads' unpaid tokens) that this
    migration will not make unilaterally by guessing a sentinel.
    """
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text("SELECT count(*) FROM lead_upload_tokens WHERE expires_at IS NULL")
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            f"Cannot downgrade c6fcc8bae2f1: {null_count} row(s) in "
            "lead_upload_tokens have expires_at IS NULL. This is expected, "
            "legitimate state for any Lead sent an upload link (Stage 3) who "
            "has not yet paid (SPEC-0001 D-8) — not stale or incomplete data. "
            "Re-adding NOT NULL requires deciding what to do with these rows "
            "first; this migration deliberately does not backfill a sentinel "
            "value, because any sentinel would misrepresent those Leads' "
            "payment-gate state to src/api/upload.py's _resolve_token(). "
            "Resolve manually, then retry the downgrade."
        )
    op.alter_column(
        "lead_upload_tokens", "expires_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
    )
