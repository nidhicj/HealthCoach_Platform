# PHASE-04 — Payments (F4, architecture resolved 2026-07-08, D-27) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each HC connects their own Razorpay account (pasting their own `key_id`/`key_secret`, generated after the HC completes their own KYC directly with Razorpay). From a client's page, the HC sets a fee, generates a payment link, and shares it themselves (copy button). Money flows client → HC's own Razorpay account directly; Tapas never touches it and is never the merchant of record (SPEC-0001 D-27). Tapas only creates the link via the HC's credentials and reads back status via a webhook. V1 scope is deliberately narrow: two payment states (`pending`/`failed`/`paid` — see Design Decision 5 for why this is three, not the two D-27's prose describes), no partial-payment tracking, no refund flow in Tapas, no recurring/subscription billing.

**Architecture:** A new `razorpay_connections` table (one row per HC, `UNIQUE` on `hc_user_id`) stores each HC's own Razorpay `key_id` (plaintext — not secret, needed to display "Connected as `rzp_live_xxxx`" in Settings) plus `key_secret` and a per-HC Razorpay **webhook secret** together in one Fernet-encrypted JSON blob, reusing the exact `EncryptedJSON` `TypeDecorator` already built for `google_calendar_connections.credentials` (ADR-0007's pattern, generalized by the calendar-integration work per D-30) — a new, separate encryption key (`razorpay_encryption_key`) so a breach of one key doesn't expose the other, matching the calendar connection's own precedent of a dedicated key per credential table. A new `payments` table (one row per generated link, not one row per client — an HC can generate several over a client's course) holds the Razorpay Payment Link's identifiers and the tracked status. All external Razorpay HTTP calls go through raw `httpx` requests via the existing `make_http_client()` helper (`backend/src/lib/http.py`) with HTTP Basic Auth (`key_id`, `key_secret`) — mirroring this codebase's established precedent of calling third-party REST APIs directly rather than adding a vendor SDK dependency (see `calendar.py`'s raw Google Calendar REST calls, and the R2 client's own "no boto3" precedent) rather than adding the official `razorpay` PyPI package. Webhook signature verification is implemented directly with Python's stdlib `hmac`/`hashlib` (HMAC-SHA256 over the raw request body, per Razorpay's documented scheme) — no SDK needed for this either. The webhook receiver is a single, unauthenticated, shared endpoint (Razorpay does not know about Tapas's per-HC JWT auth) — Design Decision 2 covers how it identifies which HC's webhook secret to verify against before trusting the payload.

**Tech Stack:** FastAPI/SQLAlchemy async backend, Next.js/TypeScript frontend, Zod for API schema validation, Alembic for migrations. Same stack as prior Unit_004 phases — no new backend dependency (deliberately not adding the `razorpay` PyPI package, see Architecture above).

---

## Design decisions flagged for SoJo's review (spec left these implicit)

1. **Payment Links API, not raw Orders API.** SPEC-0001's data-model sketch names a `razorpay_order_id` column and the HC journey says "clicks 'Generate payment link' → link created and displayed" — a single HC action, not a two-step order-then-checkout-page flow. Razorpay's [Payment Links API](https://razorpay.com/docs/api/payments/payment-links/) (`POST /v1/payment_links`) creates a shareable hosted checkout page in one call and *itself* creates an underlying Order — its response includes both the Payment Link's own `id` (`plink_...`) and `order_id`. Resolution used here: call the Payment Links API only; never call the separate Orders API directly. `payments.razorpay_order_id` is populated from the Payment Link response's own `order_id` field, not from a separate order-creation call. Please confirm this matches your intent — the alternative (raw Orders API + a custom-built checkout page) is far more build effort for identical v1 behavior and isn't implied anywhere in the HC/client journeys.

2. **Webhook receiver must identify which HC's secret to verify against, before it can be trusted.** Razorpay webhooks arrive at one URL — there's no per-HC JWT, since Razorpay itself is the caller, not a Tapas user. But each HC configures their *own* webhook secret on their *own* Razorpay dashboard (their account, their webhook, per D-27's self-onboarding model), so the receiver can't just try "the" secret — there are as many secrets as connected HCs. Resolution used here: parse the raw payload's `payload.payment_link.entity.id` (unverified at this point) → look up the matching `payments` row → get its `hc_user_id` → load *that* HC's `razorpay_connections.credentials["webhook_secret"]` → verify the `X-Razorpay-Signature` header against that specific secret → only then trust and process the event. If no matching `payments` row exists, or that HC has no stored webhook secret, respond `200` (not `4xx` — Razorpay retries aggressively on non-2xx, and there's nothing further to learn from a retry here) but do not update anything, and log a `warning`. This is the standard "look up the tenant by an opaque reference in the payload, verify against *that* tenant's secret" pattern — please confirm this is what you intend, since the spec's compliance note ("Tapas stores only the reference IDs needed for tracking... for verification") implies verification happens but doesn't say how a single shared endpoint picks the right secret.

3. **`payments` schema, beyond the spec's sketch.** SPEC-0001 §6 sketches `payments(id, client_id, razorpay_order_id, razorpay_payment_id, amount_paise, status, paid_at)`. This plan adds, beyond that sketch: `hc_user_id` (required for the webhook lookup in Decision 2, and for tenant-scoping the HC-facing list/generate endpoints the same way every other domain table in this codebase does — `_get_owned_client`'s pattern needs it); `razorpay_payment_link_id` (the Payment Link's own id, `UNIQUE` — the natural external key for this row, since one row = one generated link); `short_url` (the shareable checkout URL the HC copies — has to be persisted, it's only returned once at creation); `description` (what the HC typed as the reason, e.g. "March fee"); `created_at`/`updated_at`. None of these are optional — the endpoints in Tasks 5–7 can't function without them. Flagging because it's a real expansion of the documented sketch, not a literal implementation of it.

4. **Where the HC pastes Razorpay credentials, and how they're encrypted.** Resolved by direct reuse of an existing, already-Accepted pattern (ADR-0007, extended by D-30/PHASE-01e for `google_calendar_connections`): a new table `razorpay_connections`, one row per HC, `credentials` column typed `EncryptedJSON(settings_key="razorpay_encryption_key")` holding `{"key_secret": ..., "webhook_secret": ...}`; `key_id` stored as a separate plaintext column (not secret — Razorpay's own docs treat the Key ID as a public identifier, and the Settings UI needs to display it back to the HC for confirmation, e.g. "Connected as `rzp_live_A1b2C3`"). This is not new design — it is Design Decision 4's answer *because* it's a direct precedent match, not an open question. Flagging only so the reuse is explicit and reviewable, not because I think there's a real alternative worth debating.

5. **Payment status: three states, not two — a correction to D-27's prose.** D-27 says "only two states, pending or paid (no partial-payment tracking)." But SPEC-0001 §6's own data-model sketch for `payments` already lists `status ENUM(pending,paid,failed)` — three states. These two parts of the same spec disagree. Resolution used here: **three states**, matching the sketch, not the prose — because Razorpay Payment Links do reach terminal non-paid states (`expired`, `cancelled`) that aren't "pending" in any useful sense; without a `failed` state, an expired link would sit shown as "pending" forever with no way for the HC to know it needs a fresh one. This does **not** reintroduce partial-payment tracking (D-27's actual concern) — Razorpay's own `partially_paid` status is deliberately **not** one of our three states; a partial payment is mapped to `pending` in v1 (full payment or nothing, from the HC's point of view), consistent with "no partial-payment tracking." Please confirm — I'm treating the sketch as more authoritative than the summary sentence here, since the sketch is more precise, but this is exactly the kind of internal spec inconsistency the anthem (rule 2/6) says to surface rather than silently pick a side on.

6. **Settings UI location — there is no top-level Settings page yet.** The spec says "Settings: connect payment account," but the current codebase (confirmed by reading `frontend/src/app/(app)/layout.tsx`'s `NAV_LINKS` and the `settings/` directory) has no `/settings` landing page at all — only two narrow, single-purpose subpages exist (`/settings/diet-chart-templates`, `/settings/sessions`), and the "Settings" nav label currently links straight to `/settings/sessions`. Google Calendar's own connect UI (D-30) deliberately avoided this gap by living inline on the session page instead of in Settings. Resolution used here: add a new `/settings/payments` page (Task 9) and a new `NAV_LINKS` entry pointing at it directly — the same "one flat page per concern" pattern as the two existing subpages, not a new Settings hub/sub-nav (building a real Settings home page is out of scope for this plan; flagging as a suggested follow-up, not doing it here). Please confirm this is an acceptable interim structure, since it means the top nav will soon have four "Settings"-ish entries with no grouping.

7. **Not sending client PII to Razorpay's Payment Link `customer` object.** Razorpay's Payment Links API accepts an optional `customer` object (name/contact/email) that, if included, both pre-fills Razorpay's own checkout page *and* triggers Razorpay's own SMS/email notification to the client. Resolution used here: omit `customer` and set `notify: {"sms": false, "email": false}` entirely — the HC shares the link themselves (per the spec's HC journey, step 4: "HC shares the link... copy button"), so Razorpay's own notify path is redundant, and this avoids transmitting the client's name/email/phone to a sub-processor (Razorpay) for a purpose (Razorpay-sent notifications) the product doesn't actually use. `reference_id` is set to our own internal `payments.id` (a UUID, well under Razorpay's 40-character limit) so a payment can be correlated back to Tapas from the Razorpay dashboard without any client PII crossing over. Flagging since this is a real, deliberate data-minimization choice the spec doesn't explicitly make — please confirm it doesn't conflict with anything HCs expect Razorpay itself to do (e.g. some HCs may *want* Razorpay's own reminder SMS).

8. **Credential sanity-check on save.** Not in the spec at all. Resolution used here (Task 4): when the HC saves `key_id`/`key_secret`, make one lightweight authenticated call to Razorpay (`GET /v1/payments?count=1`) before persisting anything, to fail fast on a typo'd or revoked key rather than silently storing bad credentials that only surface as a failure the next time the HC tries to generate a real payment link for a client. Mocked in tests per the Global Constraints below. Flagging as an addition beyond spec, in the spirit of rule 1 (not lazy on important questions) — happy to cut it if SoJo prefers zero live-validation coupling to Razorpay at save time.

---

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before backend commands
- Tests hit a real PostgreSQL DB (`tapas_test`) — no mocking the DB
- After the migrations land, run `alembic upgrade head` against `tapas_dev` too (not just `tapas_test`, which rebuilds fresh every test run and would hide drift): `DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/tapas_dev alembic upgrade head`
- **Mock every Razorpay HTTP call and every webhook signature in tests — never call the real Razorpay API, and never use a real Razorpay webhook secret, from CI or local test runs.** Follow the existing `_mock_http()` pattern already used for OpenRouter/Google Calendar test mocking in this codebase (see e.g. `backend/tests/integration/test_scheduler.py`'s `patch(...)` usage) — patch `make_http_client` (or the specific httpx call) at the test boundary.
- No new backend dependency — Razorpay REST calls go through the existing `httpx`/`make_http_client()` stack; webhook signature verification uses stdlib `hmac`/`hashlib` only (see Architecture)
- Every new HC-facing endpoint follows this codebase's existing tenant-scoping convention: cross-tenant access returns `404`, never `403` (don't leak existence) — reuse `clients.py`'s `_get_owned_client` pattern by importing it, not duplicating it, since payments always hang off a specific client
- The webhook receiver (`POST /api/webhooks/razorpay`) is the one deliberate exception to normal auth — it has no `HcClaimsDep`/`ClientClaimsDep` dependency at all, since Razorpay itself is the caller; its own security boundary is the per-HC signature check (Design Decision 2), not a JWT
- `razorpay_connections.credentials` and any log line touching it must never log `key_secret`/`webhook_secret` in plaintext — structured log calls in this plan log only outcome/status fields, never credential values (matches the existing PII-redaction convention already enforced for other structured logs in this codebase, e.g. `calendar.py`'s `_log()` helpers)
- No refund flow, no recurring/subscription billing, no partial-payment state beyond Design Decision 5's `failed` addition — all explicitly out of scope per D-27

---

## Task 1: Settings — `razorpay_encryption_key` + `.env.example`

**Files:**
- Modify: `backend/src/config.py`
- Modify: `backend/.env.example` (or repo-root `.env.example`, whichever this repo actually uses — check before editing)
- Test: `backend/tests/unit/test_config.py` (extend, if it exists — check first; if not, add assertions to whatever existing settings test covers `google_calendar_encryption_key`)

**Interfaces:**
- Produces: `Settings.razorpay_encryption_key: str` — consumed by Task 2's `EncryptedJSON` column.

---

- [ ] **Step 1.1: Write the failing test**

Find the existing test that asserts `Settings` loads `google_calendar_encryption_key` (grep `backend/tests/` for it first — do not guess its name or location) and add a parallel assertion for `razorpay_encryption_key`, following that exact test's style.

- [ ] **Step 1.2: Run — confirm failure**

```bash
cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate && python -m pytest tests/ -k razorpay_encryption -v
```

Expected: FAIL — attribute doesn't exist yet.

- [ ] **Step 1.3: Implement**

In `backend/src/config.py`, add alongside the existing encryption-key settings:

```python
    razorpay_encryption_key: str = ""
```

Add to `.env.example` (wherever the existing `GOOGLE_CALENDAR_ENCRYPTION_KEY` line lives):

```
RAZORPAY_ENCRYPTION_KEY=
```

- [ ] **Step 1.4: Run — confirm pass**

```bash
cd backend && python -m pytest tests/ -k razorpay_encryption -v
```

- [ ] **Step 1.5: Commit**

```bash
git add backend/src/config.py backend/.env.example
git commit -m "feat(payments): add razorpay_encryption_key setting (PHASE-04 Task 1, D-27)"
```

---

## Task 2: `razorpay_connections` table + model

**Files:**
- Create: `backend/src/db/models/payments.py`
- Modify: `backend/src/db/models/__init__.py` (re-export)
- Create: Alembic migration
- Test: `backend/tests/unit/test_model_razorpay_connection.py`

**Interfaces:**
- Produces: `RazorpayConnection` model — `id, hc_user_id (UNIQUE FK), key_id, credentials (EncryptedJSON), connected_at, updated_at`. Consumed by Tasks 4–6.

---

- [ ] **Step 2.1: Write the failing test**

```python
# backend/tests/unit/test_model_razorpay_connection.py
"""Unit test: RazorpayConnection model exists with the right columns and types."""
from src.db.models.payments import RazorpayConnection
from src.db.encrypted_json import EncryptedJSON


def test_razorpay_connection_has_expected_columns():
    cols = RazorpayConnection.__table__.columns
    assert "id" in cols
    assert "hc_user_id" in cols
    assert cols["hc_user_id"].unique is True
    assert "key_id" in cols
    assert cols["key_id"].nullable is False
    assert "credentials" in cols
    assert isinstance(cols["credentials"].type, EncryptedJSON)
    assert cols["credentials"].type._settings_key == "razorpay_encryption_key"
    assert "connected_at" in cols
    assert "updated_at" in cols
```

- [ ] **Step 2.2: Run — confirm failure**

```bash
cd backend && python -m pytest tests/unit/test_model_razorpay_connection.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.db.models.payments'`.

- [ ] **Step 2.3: Implement the model**

```python
# backend/src/db/models/payments.py
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.encrypted_json import EncryptedJSON


class RazorpayConnection(Base):
    """An HC's own, self-onboarded Razorpay account credentials (SPEC-0001 D-27).

    One row per HC. `key_id` is Razorpay's public Key ID (not secret — shown
    back to the HC in Settings for confirmation). `credentials` holds
    `{"key_secret": ..., "webhook_secret": ...}`, Fernet-encrypted under a
    dedicated key (razorpay_encryption_key), separate from every other
    encrypted-credential table in this codebase (ADR-0007's pattern).
    """
    __tablename__ = "razorpay_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    key_id: Mapped[str] = mapped_column(Text, nullable=False)
    credentials: Mapped[dict] = mapped_column(
        EncryptedJSON(settings_key="razorpay_encryption_key"), nullable=False
    )
    connected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
```

Add to `backend/src/db/models/__init__.py`:

```python
from src.db.models.payments import RazorpayConnection
```

and to `__all__`: `"RazorpayConnection",`

- [ ] **Step 2.4: Run — confirm pass**

```bash
cd backend && python -m pytest tests/unit/test_model_razorpay_connection.py -v
```

- [ ] **Step 2.5: Check current migration head, then generate the migration**

```bash
cd backend && alembic heads
```

Confirm the reported head (expected `c8af0b7b55f9` per the current chain — re-verify at execution time rather than trusting this number blindly, per this repo's own convention).

```bash
cd backend && alembic revision -m "add_razorpay_connections_table"
```

Fill in the generated file:

```python
def upgrade() -> None:
    op.create_table(
        "razorpay_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("key_id", sa.Text(), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=False),
        sa.Column("connected_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("razorpay_connections")
```

(`credentials` is `sa.Text()` at the DB level — `EncryptedJSON`'s `impl = Text`, the encryption happens at the ORM boundary, not the column type, exactly like `google_calendar_connections.credentials`.)

Set `down_revision` to the head confirmed in this step.

- [ ] **Step 2.6: Apply to local dev DB**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 2.7: Commit**

```bash
git add backend/src/db/models/payments.py backend/src/db/models/__init__.py backend/alembic/versions/ backend/tests/unit/test_model_razorpay_connection.py
git commit -m "feat(db): add razorpay_connections table for self-onboarded HC credentials (D-27)"
```

---

## Task 3: `payments` table + model

**Files:**
- Modify: `backend/src/db/models/payments.py` (add `Payment` alongside `RazorpayConnection`)
- Modify: `backend/src/db/models/__init__.py`
- Create: Alembic migration
- Test: `backend/tests/unit/test_model_payment.py`

**Interfaces:**
- Produces: `Payment` model — `id, client_id, hc_user_id, razorpay_payment_link_id (UNIQUE), razorpay_order_id, razorpay_payment_id (nullable), amount_paise, description, short_url, status, paid_at (nullable), created_at, updated_at`. Consumed by Tasks 5–8.

---

- [ ] **Step 3.1: Write the failing test**

```python
# backend/tests/unit/test_model_payment.py
"""Unit test: Payment model exists with the right columns, types, and status values (Design Decision 5)."""
from src.db.models.payments import Payment


def test_payment_has_expected_columns():
    cols = Payment.__table__.columns
    for name in (
        "id", "client_id", "hc_user_id", "razorpay_payment_link_id", "razorpay_order_id",
        "razorpay_payment_id", "amount_paise", "description", "short_url", "status",
        "paid_at", "created_at", "updated_at",
    ):
        assert name in cols, f"missing column: {name}"
    assert cols["razorpay_payment_link_id"].unique is True
    assert cols["razorpay_payment_id"].nullable is True
    assert cols["paid_at"].nullable is True
    assert cols["amount_paise"].nullable is False


def test_payment_status_default_is_pending():
    p = Payment(
        client_id="00000000-0000-0000-0000-000000000000",
        hc_user_id="00000000-0000-0000-0000-000000000000",
        razorpay_payment_link_id="plink_test",
        razorpay_order_id="order_test",
        amount_paise=500000,
        description="Test fee",
        short_url="https://rzp.io/i/test",
    )
    assert p.status == "pending"
```

- [ ] **Step 3.2: Run — confirm failure**

```bash
cd backend && python -m pytest tests/unit/test_model_payment.py -v
```

Expected: FAIL — `Payment` doesn't exist yet.

- [ ] **Step 3.3: Implement**

Add to `backend/src/db/models/payments.py`:

```python
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PGUUID  # if not already imported above


class Payment(Base):
    """One row per generated Razorpay Payment Link (SPEC-0001 D-27, F4).

    Not one row per client — an HC generates a fresh link by hand whenever
    payment is next due (no recurring billing in v1), so a client can
    accumulate several rows over a course. `status` is three-valued
    (Design Decision 5): pending -> paid (webhook `payment_link.paid`) or
    pending -> failed (link expired/cancelled at Razorpay, or a payment
    attempt failed outright) - never partially_paid, which Razorpay itself
    supports but this plan deliberately does not track (D-27).
    """
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'paid', 'failed')", name="ck_payments_status"),
        Index("idx_payments_client_created", "client_id", "created_at"),
        Index("idx_payments_razorpay_order_id", "razorpay_order_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    razorpay_payment_link_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    razorpay_order_id: Mapped[str] = mapped_column(Text, nullable=False)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    short_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
```

(Reconcile imports at the top of the file — `Integer`, `CheckConstraint`, `Index` need adding to the existing `from sqlalchemy import ...` line; do not duplicate the import line, extend it.)

Update `backend/src/db/models/__init__.py`: add `Payment` to the `from src.db.models.payments import ...` line and to `__all__`.

- [ ] **Step 3.4: Run — confirm pass**

```bash
cd backend && python -m pytest tests/unit/test_model_payment.py -v
```

- [ ] **Step 3.5: Generate + fill the migration**

```bash
cd backend && alembic heads   # confirm current head is the razorpay_connections migration from Task 2
cd backend && alembic revision -m "add_payments_table"
```

```python
def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("razorpay_payment_link_id", sa.Text(), unique=True, nullable=False),
        sa.Column("razorpay_order_id", sa.Text(), nullable=False),
        sa.Column("razorpay_payment_id", sa.Text(), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("short_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint("ck_payments_status", "payments", "status IN ('pending', 'paid', 'failed')")
    op.create_index("idx_payments_client_created", "payments", ["client_id", "created_at"])
    op.create_index("idx_payments_razorpay_order_id", "payments", ["razorpay_order_id"])


def downgrade() -> None:
    op.drop_index("idx_payments_razorpay_order_id", table_name="payments")
    op.drop_index("idx_payments_client_created", table_name="payments")
    op.drop_constraint("ck_payments_status", "payments", type_="check")
    op.drop_table("payments")
```

- [ ] **Step 3.6: Apply to local dev DB**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 3.7: Commit**

```bash
git add backend/src/db/models/payments.py backend/src/db/models/__init__.py backend/alembic/versions/ backend/tests/unit/test_model_payment.py
git commit -m "feat(db): add payments table, 3-state status (D-27, Design Decision 5)"
```

---

## Task 4: Backend — Razorpay credentials connect/status endpoints

**Files:**
- Create: `backend/src/api/payments.py`
- Modify: `backend/src/main.py` (register router)
- Test: `backend/tests/integration/test_payments_credentials.py`

**Interfaces:**
- Produces: `POST /api/settings/razorpay-credentials -> RazorpayConnectionStatusOut` (save/replace), `GET /api/settings/razorpay-credentials -> RazorpayConnectionStatusOut` (read status). Consumed by Task 9 (frontend Settings page).

---

- [ ] **Step 4.1: Write the failing tests**

```python
# backend/tests/integration/test_payments_credentials.py
"""Integration tests for connecting/reading an HC's own Razorpay credentials (D-27)."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest


def _mock_http(status_code: int = 200):
    class _FakeResp:
        def __init__(self, code):
            self.status_code = code
        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("bad", request=None, response=self)  # type: ignore[arg-type]

    class _FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, *a, **kw):
            return _FakeResp(status_code)

    return _FakeClient()


@pytest.mark.asyncio
async def test_connect_saves_credentials_and_returns_masked_status(http_client, hc_headers):
    with patch("src.api.payments.make_http_client", return_value=_mock_http(200)):
        r = await http_client.post(
            "/api/settings/razorpay-credentials",
            headers=hc_headers,
            json={"key_id": "rzp_test_ABC123", "key_secret": "supersecret", "webhook_secret": "whsec_xyz"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] is True
    assert body["key_id"] == "rzp_test_ABC123"
    assert "key_secret" not in body
    assert "webhook_secret" not in body


@pytest.mark.asyncio
async def test_connect_rejects_invalid_credentials(http_client, hc_headers):
    with patch("src.api.payments.make_http_client", return_value=_mock_http(401)):
        r = await http_client.post(
            "/api/settings/razorpay-credentials",
            headers=hc_headers,
            json={"key_id": "rzp_test_bad", "key_secret": "wrong", "webhook_secret": "whsec_xyz"},
        )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_status_reports_not_connected_by_default(http_client, hc2_headers):
    r = await http_client.get("/api/settings/razorpay-credentials", headers=hc2_headers)
    assert r.status_code == 200
    assert r.json()["connected"] is False
```

Fixture note: check `backend/tests/integration/conftest.py`'s exact `make_http_client` usage/mocking convention for existing tests (e.g. how `test_scheduler.py`/calendar tests mock outbound HTTP) before writing this — align the mock shape with whatever pattern already exists rather than inventing a second one, adjusting the fake response/client above if the existing convention differs.

- [ ] **Step 4.2: Run — confirm failure**

```bash
cd backend && pytest tests/integration/test_payments_credentials.py -v
```

Expected: FAIL — module/routes don't exist.

- [ ] **Step 4.3: Implement**

```python
# backend/src/api/payments.py
"""HC-facing payment endpoints (F4, SPEC-0001 D-27): Razorpay credential
connection, payment-link generation, payment history, and the shared
webhook receiver. See PHASE-04 for design decisions and full context.
"""
import hashlib
import hmac
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.clients import _get_owned_client
from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models import Payment, RazorpayConnection
from src.lib.http import make_http_client
from src.telemetry.log import get_logger

router = APIRouter(tags=["payments"])

_RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


class RazorpayConnectIn(BaseModel):
    key_id: str
    key_secret: str
    webhook_secret: str


class RazorpayConnectionStatusOut(BaseModel):
    connected: bool
    key_id: str | None = None
    connected_at: datetime | None = None


@router.post("/api/settings/razorpay-credentials")
async def connect_razorpay(
    body: RazorpayConnectIn,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> RazorpayConnectionStatusOut:
    """Save (or replace) this HC's own Razorpay credentials.

    Sanity-checks the credentials with one lightweight authenticated call
    to Razorpay before persisting anything (Design Decision 8) — fails
    fast on a typo'd or revoked key rather than storing bad credentials
    silently.
    """
    async with make_http_client() as client:
        try:
            resp = await client.get(
                f"{_RAZORPAY_API_BASE}/payments",
                params={"count": 1},
                auth=(body.key_id, body.key_secret),
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            get_logger().info("razorpay_credentials_check", outcome="rejected", hc_id=hc_id)
            raise HTTPException(status_code=400, detail="Invalid Razorpay credentials") from exc

    existing = (await db.execute(
        select(RazorpayConnection).where(RazorpayConnection.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()

    if existing is None:
        existing = RazorpayConnection(
            hc_user_id=UUID(hc_id),
            key_id=body.key_id,
            credentials={"key_secret": body.key_secret, "webhook_secret": body.webhook_secret},
        )
        db.add(existing)
    else:
        existing.key_id = body.key_id
        existing.credentials = {"key_secret": body.key_secret, "webhook_secret": body.webhook_secret}

    await db.flush()
    await db.commit()
    get_logger().info("razorpay_credentials_check", outcome="connected", hc_id=hc_id)

    return RazorpayConnectionStatusOut(connected=True, key_id=existing.key_id, connected_at=existing.connected_at)


@router.get("/api/settings/razorpay-credentials")
async def get_razorpay_credentials_status(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> RazorpayConnectionStatusOut:
    connection = (await db.execute(
        select(RazorpayConnection).where(RazorpayConnection.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()

    if connection is None:
        return RazorpayConnectionStatusOut(connected=False)

    return RazorpayConnectionStatusOut(
        connected=True, key_id=connection.key_id, connected_at=connection.connected_at,
    )
```

Register in `backend/src/main.py` (alongside the other routers):

```python
from src.api.payments import router as payments_router
...
app.include_router(payments_router)
```

- [ ] **Step 4.4: Run — confirm pass**

```bash
cd backend && pytest tests/integration/test_payments_credentials.py -v
```

- [ ] **Step 4.5: Full backend suite — confirm no regressions**

```bash
cd backend && pytest -x
```

- [ ] **Step 4.6: Commit**

```bash
git add backend/src/api/payments.py backend/src/main.py backend/tests/integration/test_payments_credentials.py
git commit -m "feat(payments): HC connects own Razorpay credentials, validated + encrypted (D-27, Task 4)"
```

---

## Task 5: Backend — Generate payment link endpoint

**Files:**
- Modify: `backend/src/api/payments.py`
- Test: `backend/tests/integration/test_payments_generate_link.py`

**Interfaces:**
- Consumes: `_get_owned_client` (Task 4 import), `RazorpayConnection` (Task 2).
- Produces: `POST /api/clients/{client_id}/payments -> PaymentOut`. Consumed by Task 11 (frontend Financials section).

---

- [ ] **Step 5.1: Write the failing tests**

```python
# backend/tests/integration/test_payments_generate_link.py
"""Integration tests for POST /clients/{id}/payments — generate a Razorpay Payment Link (D-27)."""
from unittest.mock import patch

import pytest

from src.db.models import RazorpayConnection


async def _connect_razorpay(db, hc_user):
    conn = RazorpayConnection(
        hc_user_id=hc_user.id,
        key_id="rzp_test_ABC123",
        credentials={"key_secret": "supersecret", "webhook_secret": "whsec_xyz"},
    )
    db.add(conn)
    await db.flush()
    await db.commit()
    return conn


def _fake_payment_link_response():
    class _FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "id": "plink_Qge173R2Kr70NZ",
                "order_id": "order_Qge1CG0YA4ydIP",
                "short_url": "https://rzp.io/i/abc123",
                "status": "created",
            }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _FakeResp()

    return _FakeClient()


@pytest.mark.asyncio
async def test_generate_link_creates_pending_payment_row(http_client, hc_headers, hc_user, client_rec, db):
    await _connect_razorpay(db, hc_user)

    with patch("src.api.payments.make_http_client", return_value=_fake_payment_link_response()):
        r = await http_client.post(
            f"/api/clients/{client_rec.id}/payments",
            headers=hc_headers,
            json={"amount_rupees": 5000, "description": "March fee"},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["amount_paise"] == 500000
    assert body["short_url"] == "https://rzp.io/i/abc123"
    assert body["razorpay_payment_link_id"] == "plink_Qge173R2Kr70NZ"


@pytest.mark.asyncio
async def test_generate_link_requires_connected_razorpay_account(http_client, hc_headers, client_rec):
    r = await http_client.post(
        f"/api/clients/{client_rec.id}/payments",
        headers=hc_headers,
        json={"amount_rupees": 5000, "description": "March fee"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "razorpay_not_connected"


@pytest.mark.asyncio
async def test_generate_link_cross_tenant_returns_404(http_client, hc2_headers, client_rec):
    r = await http_client.post(
        f"/api/clients/{client_rec.id}/payments",
        headers=hc2_headers,
        json={"amount_rupees": 5000, "description": "March fee"},
    )
    assert r.status_code == 404
```

- [ ] **Step 5.2: Run — confirm failure**

```bash
cd backend && pytest tests/integration/test_payments_generate_link.py -v
```

- [ ] **Step 5.3: Implement**

Add to `backend/src/api/payments.py`:

```python
class PaymentGenerateIn(BaseModel):
    amount_rupees: int
    description: str


class PaymentOut(BaseModel):
    id: UUID
    client_id: UUID
    razorpay_payment_link_id: str
    razorpay_order_id: str
    razorpay_payment_id: str | None
    amount_paise: int
    description: str
    short_url: str
    status: str
    paid_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/api/clients/{client_id}/payments", status_code=201)
async def generate_payment_link(
    client_id: UUID,
    body: PaymentGenerateIn,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> PaymentOut:
    await _get_owned_client(db, client_id, hc_id)

    connection = (await db.execute(
        select(RazorpayConnection).where(RazorpayConnection.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=409, detail="razorpay_not_connected")

    amount_paise = body.amount_rupees * 100

    async with make_http_client() as client:
        try:
            resp = await client.post(
                f"{_RAZORPAY_API_BASE}/payment_links",
                auth=(connection.key_id, connection.credentials["key_secret"]),
                json={
                    "amount": amount_paise,
                    "currency": "INR",
                    "description": body.description,
                    # No `customer`/notify — the HC shares the link themselves;
                    # avoids sending client PII to Razorpay (Design Decision 7).
                    "notify": {"sms": False, "email": False},
                    "reminder_enable": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            get_logger().warning("razorpay_payment_link_create", outcome="error", hc_id=hc_id)
            raise HTTPException(status_code=502, detail="payment_link_create_failed") from exc

    payment = Payment(
        client_id=client_id,
        hc_user_id=UUID(hc_id),
        razorpay_payment_link_id=data["id"],
        razorpay_order_id=data["order_id"],
        amount_paise=amount_paise,
        description=body.description,
        short_url=data["short_url"],
        status="pending",
    )
    db.add(payment)
    await db.flush()
    await db.commit()

    get_logger().info("razorpay_payment_link_create", outcome="success", hc_id=hc_id, client_id=str(client_id))
    return PaymentOut.model_validate(payment)
```

Set `reference_id` — note it's omitted above pending Task 5.3's implementer double-checking Razorpay's field name/limit (`reference_id`, max 40 chars) and adding `"reference_id": str(payment_placeholder_id)` if the API rejects link creation without it; the payload above is otherwise standards-first per Design Decision 1's cited endpoint. (Flagging inline: `payments.id` doesn't exist yet at request-build time since the row isn't created until after the API call succeeds — if `reference_id` proves required in practice, generate a `uuid4()` client-side before the call and use that as both `reference_id` and, on success, as the new row's primary key via `Payment(id=..., ...)`.)

- [ ] **Step 5.4: Run — confirm pass**

```bash
cd backend && pytest tests/integration/test_payments_generate_link.py -v
```

- [ ] **Step 5.5: Commit**

```bash
git add backend/src/api/payments.py backend/tests/integration/test_payments_generate_link.py
git commit -m "feat(payments): generate Razorpay payment link for a client (D-27, Task 5)"
```

---

## Task 6: Backend — Webhook receiver

**Files:**
- Modify: `backend/src/api/payments.py`
- Test: `backend/tests/integration/test_payments_webhook.py`

**Interfaces:**
- Produces: `POST /api/webhooks/razorpay` — no auth dependency (Design Decision 2). Terminal endpoint; nothing downstream consumes its return value beyond the `200`/`400` status Razorpay itself reads.

---

- [ ] **Step 6.1: Write the failing tests**

```python
# backend/tests/integration/test_payments_webhook.py
"""Integration tests for POST /api/webhooks/razorpay — signature verification
per-HC (Design Decision 2) and status transitions (Design Decision 5)."""
import hashlib
import hmac
import json

import pytest

from src.db.models import Payment, RazorpayConnection


def _sign(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


async def _make_connected_payment(db, hc_user, client_rec, *, webhook_secret="whsec_xyz"):
    conn = RazorpayConnection(
        hc_user_id=hc_user.id, key_id="rzp_test_ABC123",
        credentials={"key_secret": "supersecret", "webhook_secret": webhook_secret},
    )
    db.add(conn)
    payment = Payment(
        client_id=client_rec.id, hc_user_id=hc_user.id,
        razorpay_payment_link_id="plink_Qge173R2Kr70NZ", razorpay_order_id="order_Qge1CG0YA4ydIP",
        amount_paise=500000, description="March fee", short_url="https://rzp.io/i/abc123",
    )
    db.add(payment)
    await db.flush()
    await db.commit()
    return payment


def _paid_payload(plink_id: str, order_id: str) -> dict:
    return {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {"entity": {"id": plink_id, "order_id": order_id, "status": "paid"}},
            "payment": {"entity": {"id": "pay_Qge2RkVj3jwLha", "order_id": order_id, "status": "captured"}},
        },
    }


@pytest.mark.asyncio
async def test_webhook_marks_payment_paid_with_valid_signature(http_client, hc_user, client_rec, db):
    payment = await _make_connected_payment(db, hc_user, client_rec)
    body = _paid_payload(payment.razorpay_payment_link_id, payment.razorpay_order_id)
    raw = json.dumps(body).encode()
    sig = _sign("whsec_xyz", raw)

    r = await http_client.post(
        "/api/webhooks/razorpay", content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert r.status_code == 200, r.text

    await db.refresh(payment)
    assert payment.status == "paid"
    assert payment.razorpay_payment_id == "pay_Qge2RkVj3jwLha"
    assert payment.paid_at is not None


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature_without_updating_row(http_client, hc_user, client_rec, db):
    payment = await _make_connected_payment(db, hc_user, client_rec)
    body = _paid_payload(payment.razorpay_payment_link_id, payment.razorpay_order_id)
    raw = json.dumps(body).encode()
    bad_sig = _sign("wrong-secret", raw)

    r = await http_client.post(
        "/api/webhooks/razorpay", content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": bad_sig},
    )
    assert r.status_code == 400

    await db.refresh(payment)
    assert payment.status == "pending"


@pytest.mark.asyncio
async def test_webhook_unknown_payment_link_returns_200_without_error(http_client):
    body = _paid_payload("plink_does_not_exist", "order_does_not_exist")
    raw = json.dumps(body).encode()
    r = await http_client.post(
        "/api/webhooks/razorpay", content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "irrelevant"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_webhook_expired_link_marks_payment_failed(http_client, hc_user, client_rec, db):
    payment = await _make_connected_payment(db, hc_user, client_rec)
    body = {
        "event": "payment_link.expired",
        "payload": {"payment_link": {"entity": {"id": payment.razorpay_payment_link_id, "status": "expired"}}},
    }
    raw = json.dumps(body).encode()
    sig = _sign("whsec_xyz", raw)

    r = await http_client.post(
        "/api/webhooks/razorpay", content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert r.status_code == 200

    await db.refresh(payment)
    assert payment.status == "failed"
```

Fixture note: confirm `http_client.post(..., content=raw_bytes)` is how this codebase's `httpx.AsyncClient` test fixture sends a raw, already-serialized body (rather than `json=...`, which would re-serialize and potentially reorder/re-format the payload, breaking the signature) — check `conftest.py`'s `http_client` fixture definition first; if it wraps a `TestTransport`/ASGI transport, `content=` should work identically to a normal `httpx.AsyncClient`, but verify rather than assume.

- [ ] **Step 6.2: Run — confirm failure**

```bash
cd backend && pytest tests/integration/test_payments_webhook.py -v
```

- [ ] **Step 6.3: Implement**

Add to `backend/src/api/payments.py`:

```python
def _verify_razorpay_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: DbDep) -> dict[str, str]:
    """Shared, unauthenticated webhook receiver for every connected HC's
    Razorpay account (Design Decision 2). Looks up the owning HC by the
    (unverified) payment_link id in the payload first, then verifies the
    signature against *that* HC's own stored webhook secret before trusting
    anything. Always returns 200 for "nothing to do" cases (unknown link,
    no stored secret) so Razorpay doesn't retry a case that will never
    resolve differently; returns 400 only for a signature that fails
    verification against a secret we do have.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    logger = get_logger()

    try:
        parsed: dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("razorpay_webhook", outcome="unparseable_body")
        return {"status": "ignored"}

    plink_id = parsed.get("payload", {}).get("payment_link", {}).get("entity", {}).get("id")
    if not plink_id:
        logger.warning("razorpay_webhook", outcome="no_payment_link_id")
        return {"status": "ignored"}

    payment = (await db.execute(
        select(Payment).where(Payment.razorpay_payment_link_id == plink_id)
    )).scalar_one_or_none()
    if payment is None:
        logger.warning("razorpay_webhook", outcome="unknown_payment_link")
        return {"status": "ignored"}

    connection = (await db.execute(
        select(RazorpayConnection).where(RazorpayConnection.hc_user_id == payment.hc_user_id)
    )).scalar_one_or_none()
    if connection is None:
        logger.warning("razorpay_webhook", outcome="hc_has_no_connection", hc_id=str(payment.hc_user_id))
        return {"status": "ignored"}

    webhook_secret = connection.credentials.get("webhook_secret")
    if not webhook_secret or not _verify_razorpay_signature(raw_body, signature, webhook_secret):
        logger.warning("razorpay_webhook", outcome="bad_signature", hc_id=str(payment.hc_user_id))
        raise HTTPException(status_code=400, detail="invalid_signature")

    event = parsed.get("event", "")
    if event == "payment_link.paid":
        payment_entity = parsed.get("payload", {}).get("payment", {}).get("entity", {})
        payment.status = "paid"
        payment.razorpay_payment_id = payment_entity.get("id")
        payment.paid_at = datetime.now(tz=payment.created_at.tzinfo) if payment.created_at.tzinfo else datetime.utcnow()
        logger.info("razorpay_webhook", outcome="marked_paid", hc_id=str(payment.hc_user_id))
    elif event in ("payment_link.expired", "payment_link.cancelled"):
        payment.status = "failed"
        logger.info("razorpay_webhook", outcome="marked_failed", event=event, hc_id=str(payment.hc_user_id))
    else:
        logger.info("razorpay_webhook", outcome="event_not_handled", event=event)
        return {"status": "ignored"}

    await db.commit()
    return {"status": "ok"}
```

Note on `paid_at`: use `from datetime import datetime, timezone` and simply `datetime.now(timezone.utc)` — the conditional above is overcomplicated; simplify to `payment.paid_at = datetime.now(timezone.utc)` when implementing (flagging so the implementer doesn't copy the awkward inline version verbatim).

- [ ] **Step 6.4: Run — confirm pass**

```bash
cd backend && pytest tests/integration/test_payments_webhook.py -v
```

- [ ] **Step 6.5: Full backend suite**

```bash
cd backend && pytest -x
```

- [ ] **Step 6.6: Commit**

```bash
git add backend/src/api/payments.py backend/tests/integration/test_payments_webhook.py
git commit -m "feat(payments): webhook receiver, per-HC signature verification (D-27, Task 6)"
```

---

## Task 7: Backend — List a client's payment history

**Files:**
- Modify: `backend/src/api/payments.py`
- Test: `backend/tests/integration/test_payments_list.py`

**Interfaces:**
- Produces: `GET /api/clients/{client_id}/payments -> list[PaymentOut]` (most recent first). Consumed by Task 11 (Financials section).

---

- [ ] **Step 7.1: Write the failing tests**

```python
# backend/tests/integration/test_payments_list.py
import pytest


@pytest.mark.asyncio
async def test_list_payments_returns_most_recent_first(http_client, hc_headers, hc_user, client_rec, db):
    from tests.integration.test_payments_generate_link import _connect_razorpay, _fake_payment_link_response
    from unittest.mock import patch

    await _connect_razorpay(db, hc_user)
    with patch("src.api.payments.make_http_client", return_value=_fake_payment_link_response()):
        await http_client.post(f"/api/clients/{client_rec.id}/payments", headers=hc_headers,
                                json={"amount_rupees": 5000, "description": "Feb fee"})
        await http_client.post(f"/api/clients/{client_rec.id}/payments", headers=hc_headers,
                                json={"amount_rupees": 5000, "description": "March fee"})

    r = await http_client.get(f"/api/clients/{client_rec.id}/payments", headers=hc_headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert items[0]["description"] == "March fee"  # most recent first


@pytest.mark.asyncio
async def test_list_payments_cross_tenant_returns_404(http_client, hc2_headers, client_rec):
    r = await http_client.get(f"/api/clients/{client_rec.id}/payments", headers=hc2_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_payments_empty_for_client_with_none(http_client, hc_headers, client_rec):
    r = await http_client.get(f"/api/clients/{client_rec.id}/payments", headers=hc_headers)
    assert r.status_code == 200
    assert r.json() == []
```

(Note: the same fake Payment Link response is reused across creates in the first test — Razorpay would actually return distinct `plink_...` ids per call; since `razorpay_payment_link_id` is `UNIQUE`, the fixture helper's fake response needs a unique id per call if reused as-is. Fix by parameterizing `_fake_payment_link_response` with an id, or by using distinct fakes per call in the actual test file — do not let this pass by accident with only one row created; verify `len(items) == 2` genuinely holds two distinct rows before moving on.)

- [ ] **Step 7.2: Run — confirm failure**

```bash
cd backend && pytest tests/integration/test_payments_list.py -v
```

- [ ] **Step 7.3: Implement**

Add to `backend/src/api/payments.py`:

```python
@router.get("/api/clients/{client_id}/payments")
async def list_client_payments(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> list[PaymentOut]:
    await _get_owned_client(db, client_id, hc_id)

    rows = (await db.execute(
        select(Payment)
        .where(Payment.client_id == client_id)
        .order_by(Payment.created_at.desc())
    )).scalars().all()

    return [PaymentOut.model_validate(r) for r in rows]
```

- [ ] **Step 7.4: Run — confirm pass, then full suite**

```bash
cd backend && pytest tests/integration/test_payments_list.py -v
cd backend && pytest -x
```

- [ ] **Step 7.5: Commit**

```bash
git add backend/src/api/payments.py backend/tests/integration/test_payments_list.py
git commit -m "feat(payments): list a client's payment history (Task 7)"
```

---

## Task 8: Backend — Dashboard revenue summary

**Files:**
- Modify: `backend/src/api/payments.py`
- Test: `backend/tests/integration/test_payments_summary.py`

**Interfaces:**
- Produces: `GET /api/payments/summary -> RevenueSummaryOut` — `collected_this_month_paise` (sum of `amount_paise` where `status='paid'` and `paid_at` falls in the current IST calendar month) and `outstanding_paise` (sum of `amount_paise` where `status='pending'`, regardless of month — an unpaid link doesn't stop being outstanding just because the calendar rolled over). Consumed by Task 12 (Dashboard revenue card).

---

- [ ] **Step 8.1: Write the failing tests**

```python
# backend/tests/integration/test_payments_summary.py
"""Integration tests for GET /api/payments/summary (Dashboard revenue card)."""
from datetime import datetime, timedelta, timezone

import pytest

from src.db.models import Payment


async def _make_payment(db, hc_user, client_rec, *, amount_paise, status, paid_at=None):
    p = Payment(
        client_id=client_rec.id, hc_user_id=hc_user.id,
        razorpay_payment_link_id=f"plink_{amount_paise}_{status}_{id(object())}",
        razorpay_order_id="order_x", amount_paise=amount_paise, description="fee",
        short_url="https://rzp.io/i/x", status=status, paid_at=paid_at,
    )
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_summary_sums_this_months_paid_and_all_pending(http_client, hc_headers, hc_user, client_rec, db):
    now = datetime.now(timezone.utc)
    last_month = now.replace(day=1) - timedelta(days=1)

    await _make_payment(db, hc_user, client_rec, amount_paise=500000, status="paid", paid_at=now)
    await _make_payment(db, hc_user, client_rec, amount_paise=300000, status="paid", paid_at=last_month)
    await _make_payment(db, hc_user, client_rec, amount_paise=200000, status="pending")
    await _make_payment(db, hc_user, client_rec, amount_paise=100000, status="failed")
    await db.commit()

    r = await http_client.get("/api/payments/summary", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["collected_this_month_paise"] == 500000  # last month's paid row excluded
    assert body["outstanding_paise"] == 200000  # failed row excluded, it isn't outstanding either


@pytest.mark.asyncio
async def test_summary_scoped_to_calling_hc_only(http_client, hc2_headers):
    r = await http_client.get("/api/payments/summary", headers=hc2_headers)
    assert r.status_code == 200
    assert r.json() == {"collected_this_month_paise": 0, "outstanding_paise": 0}
```

- [ ] **Step 8.2: Run — confirm failure**

```bash
cd backend && pytest tests/integration/test_payments_summary.py -v
```

- [ ] **Step 8.3: Implement**

Add to `backend/src/api/payments.py`:

```python
from sqlalchemy import func as sa_func


class RevenueSummaryOut(BaseModel):
    collected_this_month_paise: int
    outstanding_paise: int


@router.get("/api/payments/summary")
async def get_revenue_summary(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> RevenueSummaryOut:
    now = datetime.now(tz=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    collected = (await db.execute(
        select(sa_func.coalesce(sa_func.sum(Payment.amount_paise), 0)).where(
            Payment.hc_user_id == UUID(hc_id),
            Payment.status == "paid",
            Payment.paid_at >= month_start,
        )
    )).scalar_one()

    outstanding = (await db.execute(
        select(sa_func.coalesce(sa_func.sum(Payment.amount_paise), 0)).where(
            Payment.hc_user_id == UUID(hc_id),
            Payment.status == "pending",
        )
    )).scalar_one()

    return RevenueSummaryOut(collected_this_month_paise=int(collected), outstanding_paise=int(outstanding))
```

Note: `month_start` uses naive `datetime.now()` here for simplicity of the boundary comparison against a `TIMESTAMPTZ` column via asyncpg's tz-aware round-trip — reconcile timezone-awareness explicitly during implementation (use `datetime.now(timezone.utc)` and confirm the comparison behaves correctly against Postgres's `TIMESTAMPTZ`, or the IST-vs-UTC month boundary will be off by up to 5.5 hours right at month start/end — check `calendar.py`'s own `_TOKEN_EXPIRY_BUFFER`-adjacent tz-handling comment for this codebase's established defensive pattern before finalizing).

- [ ] **Step 8.4: Run — confirm pass, then full suite**

```bash
cd backend && pytest tests/integration/test_payments_summary.py -v
cd backend && pytest -x
```

- [ ] **Step 8.5: Commit**

```bash
git add backend/src/api/payments.py backend/tests/integration/test_payments_summary.py
git commit -m "feat(payments): dashboard revenue summary endpoint (Task 8)"
```

---

## Task 9: Frontend — API wrappers

**Files:**
- Create: `frontend/src/lib/api/payments.ts`
- Test: `frontend/tests/unit/payments-api.test.ts`

**Interfaces:**
- Produces: `getRazorpayStatus()`, `connectRazorpay(...)`, `generatePaymentLink(clientId, ...)`, `listClientPayments(clientId)`, `getRevenueSummary()` — consumed by Tasks 10–12.

---

- [ ] **Step 9.1: Write the failing tests**

Mirror the existing style in `frontend/tests/unit/` (e.g. `checkIns-api.test.ts` / `me-api.test.ts`) — one `it(...)` per function, mocking `fetchWithAuth`, asserting exact URL/method/body.

- [ ] **Step 9.2: Run — confirm failure**

```bash
cd frontend && npx vitest run tests/unit/payments-api.test.ts
```

- [ ] **Step 9.3: Implement**

```typescript
// frontend/src/lib/api/payments.ts
import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

export const RazorpayConnectionStatusSchema = z.object({
  connected: z.boolean(),
  key_id: z.string().nullable().optional(),
  connected_at: z.string().nullable().optional(),
});
export type RazorpayConnectionStatus = z.infer<typeof RazorpayConnectionStatusSchema>;

export async function getRazorpayStatus(): Promise<RazorpayConnectionStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/settings/razorpay-credentials`);
  if (!res.ok) throw new Error(`Get Razorpay status failed: ${res.status}`);
  return RazorpayConnectionStatusSchema.parse(await res.json());
}

export async function connectRazorpay(input: {
  key_id: string; key_secret: string; webhook_secret: string;
}): Promise<RazorpayConnectionStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/settings/razorpay-credentials`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    if (res.status === 400) throw new Error("Invalid Razorpay credentials");
    throw new Error(`Connect Razorpay failed: ${res.status}`);
  }
  return RazorpayConnectionStatusSchema.parse(await res.json());
}

export const PaymentOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  razorpay_payment_link_id: z.string(),
  razorpay_order_id: z.string(),
  razorpay_payment_id: z.string().nullable(),
  amount_paise: z.number(),
  description: z.string(),
  short_url: z.string(),
  status: z.enum(["pending", "paid", "failed"]),
  paid_at: z.string().nullable(),
  created_at: z.string(),
});
export type PaymentOut = z.infer<typeof PaymentOutSchema>;

export async function generatePaymentLink(
  clientId: string,
  input: { amount_rupees: number; description: string },
): Promise<PaymentOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/payments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    if (res.status === 409) throw new Error("Connect your Razorpay account first");
    throw new Error(`Generate payment link failed: ${res.status}`);
  }
  return PaymentOutSchema.parse(await res.json());
}

export async function listClientPayments(clientId: string): Promise<PaymentOut[]> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/payments`);
  if (!res.ok) throw new Error(`List payments failed: ${res.status}`);
  return z.array(PaymentOutSchema).parse(await res.json());
}

export const RevenueSummarySchema = z.object({
  collected_this_month_paise: z.number(),
  outstanding_paise: z.number(),
});
export type RevenueSummary = z.infer<typeof RevenueSummarySchema>;

export async function getRevenueSummary(): Promise<RevenueSummary> {
  const res = await fetchWithAuth(`${API_URL}/api/payments/summary`);
  if (!res.ok) throw new Error(`Get revenue summary failed: ${res.status}`);
  return RevenueSummarySchema.parse(await res.json());
}
```

- [ ] **Step 9.4: Run — confirm pass**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 9.5: Commit**

```bash
git add frontend/src/lib/api/payments.ts frontend/tests/unit/payments-api.test.ts
git commit -m "feat(payments): frontend API wrappers (Task 9)"
```

---

## Task 10: Frontend — `/settings/payments` page (connect Razorpay)

**Files:**
- Create: `frontend/src/app/(app)/settings/payments/page.tsx`
- Modify: `frontend/src/app/(app)/layout.tsx` (add `NAV_LINKS` entry — Design Decision 6)

**Interfaces:**
- Consumes: `getRazorpayStatus`, `connectRazorpay` (Task 9).

---

- [ ] **Step 10.1: Add the nav link**

In `frontend/src/app/(app)/layout.tsx`, extend `NAV_LINKS`:

```typescript
const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/action-items", label: "Action Items" },
  { href: "/settings/diet-chart-templates", label: "Diet Charts" },
  { href: "/settings/payments", label: "Payments" },
  { href: "/settings/sessions", label: "Settings" },
] as const;
```

(Ordering/label per Design Decision 6 — flag for SoJo if a different placement/label is preferred once a real Settings hub exists.)

- [ ] **Step 10.2: Implement the page**

```tsx
// frontend/src/app/(app)/settings/payments/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  connectRazorpay,
  getRazorpayStatus,
  type RazorpayConnectionStatus,
} from "@/lib/api/payments";

export default function SettingsPaymentsPage() {
  const [status, setStatus] = useState<RazorpayConnectionStatus | null>(null);
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRazorpayStatus().then(setStatus).catch(() => setStatus({ connected: false }));
  }, []);

  async function handleConnect() {
    setSaving(true);
    setError(null);
    try {
      const result = await connectRazorpay({ key_id: keyId, key_secret: keySecret, webhook_secret: webhookSecret });
      setStatus(result);
      setKeySecret("");
      setWebhookSecret("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">Payments</p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">Razorpay</h1>
        <p className="mt-1 font-sans text-sm text-muted-foreground">
          Connect your own Razorpay account. Money goes directly from your client to you — Tapas never holds it.
        </p>
      </div>

      {status === null ? (
        <Skeleton className="h-24 w-full" />
      ) : status.connected ? (
        <p className="font-sans text-sm text-foreground">
          Connected as <code className="font-mono">{status.key_id}</code>.
        </p>
      ) : (
        <p className="font-sans text-sm text-muted-foreground">Not connected yet.</p>
      )}

      <Separator />

      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="key_id">Key ID</Label>
          <Input id="key_id" value={keyId} onChange={(e) => setKeyId(e.target.value)} placeholder="rzp_live_..." />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="key_secret">Key Secret</Label>
          <Input id="key_secret" type="password" value={keySecret} onChange={(e) => setKeySecret(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="webhook_secret">Webhook Secret</Label>
          <Input id="webhook_secret" type="password" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} />
          <p className="font-sans text-xs text-muted-foreground">
            From your Razorpay Dashboard → Settings → Webhooks. Point the webhook URL at this Tapas instance&apos;s
            <code className="font-mono"> /api/webhooks/razorpay</code> endpoint.
          </p>
        </div>
        {error && <p className="font-sans text-xs text-destructive">{error}</p>}
        <Button onClick={handleConnect} disabled={saving || !keyId || !keySecret || !webhookSecret}>
          {saving ? "Connecting…" : "Connect Razorpay"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 10.3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 10.4: E2E test**

Add to `frontend/tests/e2e/` (new `settings-payments.spec.ts` or alongside an existing settings spec): mock `/api/settings/razorpay-credentials` GET (not connected) then POST (connected), fill the three fields, click Connect, assert "Connected as rzp_..." renders.

- [ ] **Step 10.5: Run full frontend suite**

```bash
cd frontend && npx vitest run && npx playwright test
```

- [ ] **Step 10.6: Commit**

```bash
git add "frontend/src/app/(app)/settings/payments/page.tsx" frontend/src/app/\(app\)/layout.tsx frontend/tests/e2e/
git commit -m "feat(payments): Settings page to connect Razorpay (D-27, Design Decision 6, Task 10)"
```

---

## Task 11: Frontend — Financials section on client detail

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx`

**Interfaces:**
- Consumes: `listClientPayments`, `generatePaymentLink` (Task 9).

---

- [ ] **Step 11.1: Add a `FinancialsSection` component**

**Placement note (dependency on PHASE-02b, not yet built as of this plan):** SPEC-0001 says the Financials section lives on the client detail page's **Summary tab** — but that tab structure (`<TabsContent value="summary">`, D-20) is introduced by PHASE-02b, which had not landed in this codebase as of this plan being written (confirmed by reading the current `clients/[clientId]/page.tsx` — no `TabsContent`/`activeTab` exists yet). **If PHASE-02b has landed by the time this task executes**, add `<FinancialsSection clientId={clientId} />` inside the existing `<TabsContent value="summary">` block, near the "Details" section. **If it has not**, add it as a new top-level `<section>` on the current single-page layout, in the same visual position (near "Details"), so it isn't blocked on an unrelated phase — check the file's current state first rather than assuming either way.

```tsx
import { generatePaymentLink, listClientPayments, type PaymentOut } from "@/lib/api/payments";

function FinancialsSection({ clientId }: { clientId: string }) {
  const [payments, setPayments] = useState<PaymentOut[] | null>(null);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  useEffect(() => {
    listClientPayments(clientId).then(setPayments).catch(() => setPayments([]));
  }, [clientId]);

  const current = payments?.[0] ?? null;

  async function handleGenerate() {
    setGenerating(true);
    setGenError(null);
    try {
      const created = await generatePaymentLink(clientId, {
        amount_rupees: Number(amount),
        description,
      });
      setPayments((prev) => [created, ...(prev ?? [])]);
      setAmount("");
      setDescription("");
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Failed to generate link");
    } finally {
      setGenerating(false);
    }
  }

  async function handleCopy(url: string) {
    await navigator.clipboard.writeText(url);
  }

  return (
    <section className="space-y-4 rounded-2xl border border-border bg-section-fill-02 p-6">
      <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">Financials</h2>
      <Separator />

      {current && (
        <div className="flex items-center justify-between font-sans text-sm">
          <span>₹{(current.amount_paise / 100).toLocaleString("en-IN")} — {current.description}</span>
          <span
            className={
              current.status === "paid"
                ? "text-success"
                : current.status === "failed"
                  ? "text-destructive"
                  : "text-muted-foreground"
            }
          >
            {current.status === "paid" ? "Paid" : current.status === "failed" ? "Failed / expired" : "Pending"}
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="fee-amount">Fee (₹)</Label>
          <Input id="fee-amount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-32" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="fee-description">Description</Label>
          <Input id="fee-description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="March fee" />
        </div>
        <Button onClick={handleGenerate} disabled={generating || !amount || !description}>
          {generating ? "Generating…" : "Generate payment link"}
        </Button>
      </div>
      {genError && <p className="font-sans text-xs text-destructive">{genError}</p>}

      {current && current.status !== "paid" && (
        <Button variant="outline" size="sm" onClick={() => handleCopy(current.short_url)}>
          Copy link
        </Button>
      )}

      {payments && payments.length > 1 && (
        <details className="pt-2">
          <summary className="cursor-pointer font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Past payments ({payments.length - 1})
          </summary>
          <ul className="mt-2 space-y-1">
            {payments.slice(1).map((p) => (
              <li key={p.id} className="font-sans text-sm text-muted-foreground">
                ₹{(p.amount_paise / 100).toLocaleString("en-IN")} — {p.description} — {p.status}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
```

Insert `<FinancialsSection clientId={clientId} />` per the placement note above; add `Input`/`Label` to this file's existing import block if not already imported.

- [ ] **Step 11.2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 11.3: E2E test**

Extend `frontend/tests/e2e/fixtures/mock-api.ts` to handle `/api/clients/*/payments` (GET returning `[]`, POST returning a pending payment); add a test generating a link and asserting "Pending" + a "Copy link" button appear.

- [ ] **Step 11.4: Run full frontend suite**

```bash
cd frontend && npx vitest run && npx playwright test
```

- [ ] **Step 11.5: Commit**

```bash
git add "frontend/src/app/(app)/clients/[clientId]/page.tsx" frontend/tests/e2e/
git commit -m "feat(payments): Financials section on client detail (D-27, Task 11)"
```

---

## Task 12: Frontend — Dashboard revenue card

**Files:**
- Modify: `frontend/src/app/(app)/dashboard/page.tsx`

**Interfaces:**
- Consumes: `getRevenueSummary` (Task 9).

---

- [ ] **Step 12.1: Add the revenue card**

In `frontend/src/app/(app)/dashboard/page.tsx`, add state and a fetch alongside the existing `Promise.all` in the effect (extend it to a 4th promise, or a second independent effect — prefer extending the existing `Promise.all` to keep one loading gate, matching this file's existing pattern):

```tsx
import { getRevenueSummary, type RevenueSummary } from "@/lib/api/payments";

// inside DashboardPage, alongside the other useState calls:
const [revenue, setRevenue] = useState<RevenueSummary | null>(null);

// extend the existing Promise.all in the effect:
Promise.all([
  listClients({ limit: 100 }),
  listSessions({ limit: 100 }),
  listActionItems({ status: "missed", limit: 100 }),
  getRevenueSummary(),
])
  .then(([c, s, m, r]) => {
    setClients(c.items);
    setSessions(s.items);
    setMissedItems(m.items);
    setRevenue(r);
  })
  .catch(() => setLoadError(true));
```

Add the card, right after the header block and before the "Sessions banner" section:

```tsx
      {/* Revenue card */}
      <section className="rounded-2xl border border-border bg-section-fill-02 p-5">
        {loading || revenue === null ? (
          <Skeleton className="h-10 w-64" />
        ) : (
          <div className="flex flex-wrap items-center gap-6">
            <div>
              <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                Collected this month
              </p>
              <p className="font-heading text-2xl font-black text-foreground">
                ₹{(revenue.collected_this_month_paise / 100).toLocaleString("en-IN")}
              </p>
            </div>
            <div>
              <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                Outstanding
              </p>
              <p className="font-heading text-2xl font-black text-foreground">
                ₹{(revenue.outstanding_paise / 100).toLocaleString("en-IN")}
              </p>
            </div>
          </div>
        )}
      </section>
```

- [ ] **Step 12.2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 12.3: E2E test**

Extend the dashboard's existing e2e mock fixtures to serve `/api/payments/summary`; assert both figures render.

- [ ] **Step 12.4: Run full frontend suite**

```bash
cd frontend && npx vitest run && npx playwright test
```

- [ ] **Step 12.5: Commit**

```bash
git add "frontend/src/app/(app)/dashboard/page.tsx" frontend/tests/e2e/
git commit -m "feat(payments): dashboard revenue card (D-27, Task 12)"
```

---

## Self-review

**Spec coverage check** (against SPEC-0001 F4 + D-27):

| Spec requirement | Covered by |
|---|---|
| HC self-onboards own Razorpay account, pastes own credentials, encrypted at rest | Task 2 (table + `EncryptedJSON`), Task 4 (connect endpoint) |
| Tapas never merchant of record — money flows client → HC directly | Architecture-level: Tapas only calls the Payment Links API with the HC's own credentials and never handles funds; no code path routes money through a Tapas-owned account |
| Client detail → Financials section: current course, fee, status, due date | Task 11 — fee/status/description shown; **"due date" is not implemented** — flagging as a gap, see below |
| HC enters a fee → generates payment link → link displayed | Tasks 5, 11 |
| HC shares the link (copy button) | Task 11 (`handleCopy`) |
| Dashboard revenue card: this month's collected vs. outstanding | Tasks 8, 12 |
| Webhook updates status → client card shows "Paid" | Task 6 (webhook), Task 11 (status badge on the Financials section, not yet on the Roster Board card itself — see gap below) |
| No refund flow in Tapas | Not built — matches D-27, nothing to do |
| No recurring/subscription billing | Not built — HC repeats Task 5's flow by hand each time, matches D-27 |
| Never store raw card data; only order/payment IDs + status | Task 3's `payments` schema stores only Razorpay's own ids/status/amount, never card data (Razorpay's checkout page, which this plan never touches, handles card entry entirely) |

**Gaps, flagged not silently dropped:**
- **"Due date" on the Financials section**: SPEC-0001's HC journey step 2 lists "due date" alongside fee/status, but neither the data-model sketch nor D-27's textual description defines what sets it (a due date isn't produced anywhere in the Payment Links API response, and nothing in the HC journey describes the HC entering one). Not built in this plan — needs a SoJo decision on whether it's a new, HC-entered field on `payments` (e.g. `due_date` alongside `description`) before it can be built; flagging rather than inventing it.
- **Roster Board "Paid" indicator**: SPEC-0001 §5 lists a passive "what's new" Roster Board indicator (D-24) covering "new text / check-in / meal logged" — payments aren't explicitly one of the signals D-24 enumerates, and this plan doesn't add one. Flagging as an open question (does a payment landing count as "what's new" on the Roster Board?) rather than assuming either way.
- **Design Decisions 1–8** above are all real, unresolved-by-spec choices this plan had to make to be buildable — every one is flagged for SoJo's review, not silently decided.

**Placeholder scan**: none found in the sense of `TODO`/stub code. Two spots are intentionally incomplete pending a decision, both called out explicitly rather than hidden: (a) Task 5's `reference_id` field, deferred to the implementer confirming Razorpay's actual requirement at build time; (b) the "due date" gap above.

**Type consistency check**: `PaymentOut` (backend Pydantic, Task 5) and `PaymentOutSchema` (frontend Zod, Task 9) carry the identical field set — `id, client_id, razorpay_payment_link_id, razorpay_order_id, razorpay_payment_id, amount_paise, description, short_url, status, paid_at, created_at` — both land in the same task pair (5 backend / 9 frontend) before any consumer (Tasks 10–12) is built, so there's no drift window. `status`'s three-value set (`pending`/`paid`/`failed`, Design Decision 5) is enforced at three independent layers: the Postgres `CHECK` constraint (Task 3), and the frontend Zod `z.enum(["pending", "paid", "failed"])` (Task 9) — the backend Pydantic `PaymentOut.status` is left as a plain `str` rather than a matching literal/enum type, which is a real, worth-flagging gap in defense-in-depth (a future backend bug could write an invalid status that the DB constraint catches but Pydantic's response model wouldn't). Suggested follow-up, not fixed in this plan: tighten `PaymentOut.status: Literal["pending", "paid", "failed"]`.

**Execution:** Subagent-driven, per SoJo's standing instruction (matches PHASE-01c/PHASE-02b's own note) — no execution-choice question needed.
