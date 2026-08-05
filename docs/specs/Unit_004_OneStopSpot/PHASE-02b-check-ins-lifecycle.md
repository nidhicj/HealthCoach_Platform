# PHASE-02b — Check-ins Request/Answer Lifecycle (D-21, D-22, D-23) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan builds directly on PHASE-02a (`/me/*` shell + role-aware login, already shipped) — read that file if you need its exact current state; do not re-implement anything from it.

**Goal:** The HC can request a check-in from a client (a new "awaiting answer" state); every Saturday at 9:30am IST, every active client gets the same kind of request automatically plus a reminder email; the client answers by picking any 3 of 10 fixed metrics and rating them. This is the first real content inside client detail's new **Chat** tab (D-20) and the first content on the client-facing `/me/checkins` page.

## Design decisions flagged for SoJo's review (spec left these implicit)

1. **Data model for the "pending" state.** The spec's data-model sketch says "existing check-in storage gets a new nullable field marking when the HC requested one... no new parallel table" but doesn't fully specify how "waiting for an answer" is represented before the client responds. Resolution used here: `check_ins.requested_at TIMESTAMPTZ NULL` (new column) **and** `check_ins.payload` becomes nullable. A row with `requested_at IS NOT NULL AND payload IS NULL` **is** the pending/awaiting state — it exists the moment a request is made, before any answer. When the client answers, that same row's `payload` gets filled in (not a new row). An ad hoc, client-initiated check-in (today's existing, unchanged behavior) still just inserts a row with `requested_at = NULL` and `payload` set immediately. This is additive and doesn't touch any existing row shape.
2. **What "every Saturday" actually does.** The spec lists "HC can request one" and "every Saturday, client gets an email" as separate bullets but doesn't say whether Saturday's reminder is just an email nudge or also creates the pending-request row. Resolution: Saturday's cron **creates the same kind of pending request** (if the client doesn't already have one outstanding) for every eligible client, then emails the reminder — this way the client's `/me/checkins` page always has something concrete to answer when they open the link in the email, and the HC's manual "Request now" is simply the same mechanism triggered early/out-of-band (e.g. ahead of a session).
3. **Eligibility for the Saturday reminder.** Resolution: `Client.journey_stage != "completed"` AND `Client.user_id IS NOT NULL` (has actually logged in / linked their account) AND `Client.email IS NOT NULL`. `onboarding`/`plateau`/`off_track` clients are still being actively coached and should keep getting reminders; only `completed` (course finished) is excluded.
4. **The 10 fixed metrics (D-22) — the spec never names them.** This is real product copy, not an engineering detail, and Task 8 below builds an actual UI around a concrete list — **please confirm or edit this list before/while this plan executes**: Energy levels, Sleep quality, Diet adherence, Stress levels, Hydration, Physical activity, Mood, Digestion, Motivation, Weight trend. Each is rated 1–10; the client can pick any 3, and a different 3 the following week (matches spec's explicit "provisional" note that this may need to lock to a consistent 3 later, pending pilot feedback).

**Architecture:** One migration (nullable-column addition, no data loss risk), extends the already-shipped `check_ins`/`me.py`/`check_ins.py` surfaces additively, reuses the existing scheduler-endpoint-hit-by-external-cron mechanism (`backend/src/api/scheduler.py` + `.github/workflows/scheduler.yml`) exactly as D-23 specifies, and reuses the exact Resend email pattern already in `backend/src/lib/email.py`. Frontend: the 2-tab Summary/Chat client-detail shell (D-20) is introduced in this plan (it has no content to hold before now) as a thin wrap around the existing single-page layout — zero changes to the ~660 lines of existing Summary content, just two insertion points.

**Tech stack:** Same as PHASE-02a — FastAPI/SQLAlchemy async, Next.js/TypeScript, Alembic, Vitest, Playwright. No new dependency.

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before backend commands
- Backend tests hit a real PostgreSQL DB (`tapas_test`) — no DB mocking
- After the migration lands, run `alembic upgrade head` against `tapas_dev` too (not just `tapas_test`, which rebuilds fresh every test run and would hide drift)
- `sentiment_flag`/existing `flag_check_in` HC endpoint behavior is completely untouched
- Follow this app's existing Tailwind/design-token conventions exactly (see PHASE-02a's Global Constraints for the specific classes/components already in use)
- No signed-URL/attachment work in this plan — that's PHASE-02c

---

## Task 1: Migration — `check_ins.requested_at` + nullable `payload`

**Files:**
- Create: `backend/alembic/versions/<new_revision>_add_requested_at_to_check_ins.py`
- Modify: `backend/src/db/models/coaching.py:69-79` (`CheckIn` model)

**Interfaces:**
- Produces: `CheckIn.requested_at: datetime | None`, `CheckIn.payload: dict | None` — Tasks 2–4 consume both.

- [ ] **Step 1.1: Check current migration head**

Run: `cd backend && alembic heads`
Expected: single head, currently `a1b2c3d4e5f6` (per the existing chain) — confirm before generating a new revision so it chains correctly.

- [ ] **Step 1.2: Generate the migration**

Run: `cd backend && alembic revision -m "add_requested_at_to_check_ins"`

Edit the generated file to:

```python
"""add_requested_at_to_check_ins

Revision ID: <generated>
Revises: a1b2c3d4e5f6
Create Date: <generated>
"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("check_ins", sa.Column("requested_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.alter_column("check_ins", "payload", existing_type=sa.dialects.postgresql.JSONB, nullable=True)


def downgrade() -> None:
    op.alter_column("check_ins", "payload", existing_type=sa.dialects.postgresql.JSONB, nullable=False)
    op.drop_column("check_ins", "requested_at")
```

- [ ] **Step 1.3: Update the model**

In `backend/src/db/models/coaching.py`, `CheckIn` class:

```python
class CheckIn(Base):
    __tablename__ = "check_ins"
    __table_args__ = (Index("idx_check_ins_client_created", "client_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    sentiment_flag: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
```

- [ ] **Step 1.4: Run — apply and verify**

Run: `cd backend && alembic upgrade head`
Expected: applies cleanly, no errors

Run: `cd backend && alembic upgrade head` again against dev per this repo's convention:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/tapas_dev alembic upgrade head
```
Expected: applies cleanly against `tapas_dev` too

- [ ] **Step 1.5: Commit**

```bash
git add backend/alembic/versions/ backend/src/db/models/coaching.py
git commit -m "feat(check-ins): add requested_at + nullable payload for HC-request lifecycle (PHASE-02b Task 1)"
```

---

## Task 2: Shared pending-check-in helper + updated schemas

**Files:**
- Modify: `backend/src/api/check_ins.py` (`CheckInOut` schema, lines 18–26)
- Create: `backend/src/api/_check_in_lifecycle.py` (new small shared module — avoids a circular import between `check_ins.py` and `me.py`, which already import from each other's siblings but not each other directly)
- Test: `backend/tests/unit/test_check_in_lifecycle.py` (new)

**Interfaces:**
- Produces: `async def get_or_create_pending_check_in(db: AsyncSession, client_id: UUID, hc_user_id: UUID) -> tuple[CheckIn, bool]` — returns `(row, created)`; `created=False` means a pending row already existed (caller decides what that means: 409 for the HC endpoint, "already-pending" for the cron). Tasks 3, 4, 5 all consume this.
- `CheckInOut.payload: dict | None` (was `dict`) and `CheckInOut.requested_at: datetime | None` — Tasks 3/4/5's endpoints all return this schema.

- [ ] **Step 2.1: Write the failing test**

```python
# backend/tests/unit/test_check_in_lifecycle.py
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api._check_in_lifecycle import get_or_create_pending_check_in
from src.db.models import CheckIn


@pytest.mark.asyncio
async def test_creates_pending_row_when_none_exists():
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    client_id, hc_id = uuid.uuid4(), uuid.uuid4()

    row, created = await get_or_create_pending_check_in(db, client_id, hc_id)

    assert created is True
    assert row.client_id == client_id
    assert row.hc_user_id == hc_id
    assert row.payload is None
    assert row.requested_at is not None
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_returns_existing_pending_row_without_creating_new_one():
    existing = CheckIn(
        id=uuid.uuid4(), client_id=uuid.uuid4(), hc_user_id=uuid.uuid4(),
        payload=None, requested_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = existing

    row, created = await get_or_create_pending_check_in(db, existing.client_id, existing.hc_user_id)

    assert created is False
    assert row is existing
    db.add.assert_not_called()
```

- [ ] **Step 2.2: Run — confirm failure**

Run: `cd backend && pytest tests/unit/test_check_in_lifecycle.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 2.3: Implement**

```python
# backend/src/api/_check_in_lifecycle.py
"""Shared HC-request/client-answer check-in lifecycle helper. Used by both
check_ins.py (HC-side request) and me.py (client-side submit + Saturday
cron in scheduler.py). Split out to avoid check_ins.py <-> me.py importing
each other directly.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CheckIn


async def get_or_create_pending_check_in(
    db: AsyncSession, client_id: UUID, hc_user_id: UUID,
) -> tuple[CheckIn, bool]:
    """Return (row, created). A pending row is requested_at IS NOT NULL AND
    payload IS NULL. If one already exists for this client, return it
    unchanged (created=False) rather than creating a second one.
    """
    existing = (await db.execute(
        select(CheckIn).where(
            CheckIn.client_id == client_id,
            CheckIn.requested_at.is_not(None),
            CheckIn.payload.is_(None),
        )
    )).scalar_one_or_none()
    if existing is not None:
        return existing, False

    row = CheckIn(
        client_id=client_id,
        hc_user_id=hc_user_id,
        payload=None,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row, True
```

Update `CheckInOut` in `backend/src/api/check_ins.py`:

```python
class CheckInOut(BaseModel):
    id: UUID
    client_id: UUID
    hc_user_id: UUID
    payload: dict | None
    requested_at: datetime | None
    sentiment_flag: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2.4: Run — confirm pass**

Run: `cd backend && pytest tests/unit/test_check_in_lifecycle.py -v`
Expected: both PASS

- [ ] **Step 2.5: Full backend suite — confirm no regressions**

Run: `cd backend && pytest -x`
Expected: same pass count as before (schema change is additive; no existing test asserts a closed/exact response shape for `CheckInOut` — confirmed via reading `test_me.py`/`test_check_ins.py`)

- [ ] **Step 2.6: Commit**

```bash
git add backend/src/api/_check_in_lifecycle.py backend/src/api/check_ins.py backend/tests/unit/test_check_in_lifecycle.py
git commit -m "feat(check-ins): shared get-or-create-pending helper + nullable schema fields (PHASE-02b Task 2)"
```

---

## Task 3: HC — `POST /api/clients/{client_id}/check-ins/request`

**Files:**
- Modify: `backend/src/api/check_ins.py`
- Test: `backend/tests/integration/test_check_ins.py` (extend)

**Interfaces:**
- Consumes: `get_or_create_pending_check_in` (Task 2).
- Produces: `POST /api/clients/{client_id}/check-ins/request -> CheckInOut` (201) or 409 if already pending — Task 7 (frontend `requestCheckIn`) consumes this.

- [ ] **Step 3.1: Write the failing tests**

Add to `backend/tests/integration/test_check_ins.py`, in a new `# ── POST /api/clients/{id}/check-ins/request ──` section. `_make_client` is already defined at module scope in this exact file (line 12) — call it directly, no import needed:

```python
@pytest.mark.asyncio
async def test_hc_can_request_check_in(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)

    r = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["client_id"] == client["id"]
    assert body["payload"] is None
    assert body["requested_at"] is not None


@pytest.mark.asyncio
async def test_hc_cannot_request_second_check_in_while_one_pending(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)

    r1 = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)
    assert r1.status_code == 201

    r2 = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_request_check_in_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)

    r = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc2_headers)
    assert r.status_code == 404
```

- [ ] **Step 3.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_check_ins.py -k request -v`
Expected: FAIL — 404 (route doesn't exist)

- [ ] **Step 3.3: Implement**

Add to `backend/src/api/check_ins.py`:

```python
from src.api._check_in_lifecycle import get_or_create_pending_check_in
from src.db.models import Client


@router.post("/api/clients/{client_id}/check-ins/request", status_code=status.HTTP_201_CREATED)
async def request_check_in(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> CheckInOut:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    row, created = await get_or_create_pending_check_in(db, client_id, UUID(hc_id))
    if not created:
        raise HTTPException(status_code=409, detail="A check-in request is already pending for this client")

    await db.commit()
    return CheckInOut.model_validate(row)
```

- [ ] **Step 3.4: Run — confirm pass**

Run: `cd backend && pytest tests/integration/test_check_ins.py -v`
Expected: all PASS

- [ ] **Step 3.5: Commit**

```bash
git add backend/src/api/check_ins.py backend/tests/integration/test_check_ins.py
git commit -m "feat(check-ins): HC can request a check-in from a client (PHASE-02b Task 3)"
```

---

## Task 4: Client — fill-pending-or-create-ad-hoc submit + `GET /api/me/check-ins`

**Files:**
- Modify: `backend/src/api/me.py` (`submit_check_in`)
- Test: `backend/tests/integration/test_me.py` (extend)

**Interfaces:**
- Consumes: `get_or_create_pending_check_in` is NOT used here (client fill-in is a distinct lookup, not get-or-create) — new local query for "my own pending row, if any."
- Produces: `GET /api/me/check-ins -> PaginatedList[CheckInOut]` — Task 9 (`/me/checkins` page) consumes this.

- [ ] **Step 4.1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_client_answer_fills_pending_row_not_a_new_one(http_client, hc_headers, client_headers, client_rec):
    req_r = await http_client.post(f"/api/clients/{client_rec.id}/check-ins/request", headers=hc_headers)
    pending_id = req_r.json()["id"]

    ans_r = await http_client.post(
        "/api/me/check-ins", headers=client_headers,
        json={"payload": {"metrics": {"energy": 7}}},
    )
    assert ans_r.status_code == 201
    assert ans_r.json()["id"] == pending_id  # same row, not a new one
    assert ans_r.json()["payload"] == {"metrics": {"energy": 7}}
    assert ans_r.json()["requested_at"] is not None


@pytest.mark.asyncio
async def test_client_answer_with_no_pending_request_creates_ad_hoc_row(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/check-ins", headers=client_headers,
        json={"payload": {"metrics": {"mood": 8}}},
    )
    assert r.status_code == 201
    assert r.json()["requested_at"] is None


@pytest.mark.asyncio
async def test_client_lists_own_check_ins(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(
        "/api/me/check-ins", headers=client_headers, json={"payload": {"metrics": {"energy": 5}}},
    )
    r = await http_client.get("/api/me/check-ins", headers=client_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


@pytest.mark.asyncio
async def test_client_sees_pending_request_in_own_list(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(f"/api/clients/{client_rec.id}/check-ins/request", headers=hc_headers)
    r = await http_client.get("/api/me/check-ins", headers=client_headers)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["payload"] is None
    assert items[0]["requested_at"] is not None
```

- [ ] **Step 4.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_me.py -k check_in -v`
Expected: FAIL — current `submit_check_in` always inserts a fresh row; `GET /api/me/check-ins` doesn't exist

- [ ] **Step 4.3: Implement**

Replace `submit_check_in` in `backend/src/api/me.py` and add the new list endpoint:

```python
@router.post("/check-ins", status_code=status.HTTP_201_CREATED)
async def submit_check_in(
    body: CheckInSubmit,
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> CheckInOut:
    client = await _resolve_client(db, claims, hc_id)

    pending = (await db.execute(
        select(CheckIn).where(
            CheckIn.client_id == client.id,
            CheckIn.requested_at.is_not(None),
            CheckIn.payload.is_(None),
        )
    )).scalar_one_or_none()

    if pending is not None:
        pending.payload = body.payload
        ci = pending
    else:
        ci = CheckIn(
            client_id=client.id,
            hc_user_id=UUID(hc_id),
            payload=body.payload,
        )
        db.add(ci)

    await db.flush()
    await db.commit()
    return CheckInOut.model_validate(ci)


@router.get("/check-ins")
async def list_my_check_ins(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[CheckInOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(CheckIn).where(CheckIn.client_id == client.id)

    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                CheckIn.created_at < cur_ts,
                and_(CheckIn.created_at == cur_ts, CheckIn.id < cur_id),
            )
        )

    q = q.order_by(CheckIn.created_at.desc(), CheckIn.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    return PaginatedList(items=[CheckInOut.model_validate(r) for r in rows], next_cursor=next_cursor)
```

(`CheckInOut` needs importing into `me.py` — it already is, per the existing `from src.api.check_ins import CheckInOut` at the top of the file.)

- [ ] **Step 4.4: Run — confirm pass**

Run: `cd backend && pytest tests/integration/test_me.py -v`
Expected: all PASS

- [ ] **Step 4.5: Commit**

```bash
git add backend/src/api/me.py backend/tests/integration/test_me.py
git commit -m "feat(me): client answers fill the pending request row; add GET /api/me/check-ins (PHASE-02b Task 4)"
```

---

## Task 5: Saturday 9:30am IST reminder — cron + email

**Files:**
- Modify: `backend/src/api/scheduler.py`, `.github/workflows/scheduler.yml`
- Create: `backend/src/lib/email.py` (add `send_check_in_reminder_email`)
- Test: `backend/tests/unit/test_scheduler.py` (extend), `backend/tests/integration/test_scheduler.py` (new — no integration test exists for this endpoint today)

**Interfaces:**
- Consumes: `get_or_create_pending_check_in` (Task 2), `send_check_in_reminder_email` (this task).
- Produces: `SchedulerResult.tasks_run` gains `"check_in_reminders"` when it runs.

- [ ] **Step 5.1: Write the failing unit test for the pure day-check function**

```python
# add to backend/tests/unit/test_scheduler.py
from datetime import date
from src.api.scheduler import _is_saturday_ist


def test_saturday_ist_is_true_on_a_saturday():
    assert _is_saturday_ist(date(2026, 7, 18)) is True  # a Saturday


def test_saturday_ist_is_false_on_other_days():
    assert _is_saturday_ist(date(2026, 7, 14)) is False  # a Tuesday
```

- [ ] **Step 5.2: Run — confirm failure**

Run: `cd backend && pytest tests/unit/test_scheduler.py -k saturday -v`
Expected: FAIL — function doesn't exist

- [ ] **Step 5.3: Write the failing integration test**

Uses this repo's existing `client_rec` fixture (`backend/tests/integration/conftest.py:172`) — already linked to `hc_user`/`client_user` (so `user_id` is set); the tests set `client_rec.email` inline, matching the same inline-mutation style `test_me.py`'s `_make_mom_sent` helper already uses for `client.email`:

```python
# backend/tests/integration/test_scheduler.py (new file)
from unittest.mock import patch

import pytest

from src.config import get_settings


@pytest.mark.asyncio
async def test_scheduled_tasks_creates_reminder_for_eligible_client_on_saturday(
    http_client, client_rec, db,
):
    client_rec.email = "client@example.com"
    await db.flush()
    await db.commit()

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
        )
    assert r.status_code == 200, r.text
    assert "check_in_reminders" in r.json()["tasks_run"]
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_scheduled_tasks_skips_reminder_on_non_saturday(http_client):
    with patch("src.api.scheduler._is_saturday_ist", return_value=False), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
        )
    assert r.status_code == 200
    assert "check_in_reminders" not in r.json()["tasks_run"]
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_tasks_skips_client_with_no_linked_user(http_client, client_rec, db):
    client_rec.email = "client3@example.com"
    client_rec.user_id = None  # not yet onboarded to the app
    await db.flush()
    await db.commit()

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
        )
    assert r.status_code == 200
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_tasks_still_emails_client_with_existing_pending_request(
    http_client, hc_headers, client_rec, db,
):
    client_rec.email = "client2@example.com"
    await db.flush()
    await db.commit()

    await http_client.post(f"/api/clients/{client_rec.id}/check-ins/request", headers=hc_headers)

    with patch("src.api.scheduler._is_saturday_ist", return_value=True), \
         patch("src.api.scheduler.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(
            "/internal/scheduled-tasks",
            headers={"X-Scheduler-Token": get_settings().scheduler_secret},
        )
    assert r.status_code == 200
    # Already has a pending row — still gets emailed (nudge), but no second row created
    mock_email.assert_called_once()
    count_r = await http_client.get(f"/api/clients/{client_rec.id}/check-ins", headers=hc_headers)
    assert len(count_r.json()["items"]) == 1
```

- [ ] **Step 5.4: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_scheduler.py -v`
Expected: FAIL — no such logic in `run_scheduled_tasks` yet

- [ ] **Step 5.5: Implement**

Add to `backend/src/lib/email.py`:

```python
def send_check_in_reminder_email(*, to: str, client_name: str, portal_url: str) -> None:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_client = html.escape(client_name)
    subject = "Your weekly check-in"
    safe_subject = html.escape(subject)

    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_subject}</title>
</head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #2C2C1E; background: #F7F4EE;">
  <div style="background: #5C6652; padding: 20px 24px; border-radius: 8px 8px 0 0;">
    <h1 style="color: #F7F4EE; font-size: 20px; margin: 0;">Tapas</h1>
  </div>
  <div style="background: #ffffff; padding: 28px 24px; border-radius: 0 0 8px 8px; border: 1px solid #E8EDE5;">
    <p style="font-size: 15px; margin-top: 0;">Hi {safe_client},</p>
    <p style="font-size: 15px;">It's Saturday — time for your weekly check-in. Pick any 3 metrics and rate how your week went.</p>
    <p style="margin: 24px 0;">
      <a href="{portal_url}" style="background: #5C6652; color: #F7F4EE; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">Fill in check-in</a>
    </p>
    <hr style="border: none; border-top: 1px solid #E8EDE5; margin: 20px 0;">
    <p style="font-size: 12px; color: #888;">Sent via Tapas · your health coaching platform</p>
  </div>
</body>
</html>"""

    resend.Emails.send({
        "from": _get_from_email(),
        "to": [to],
        "subject": subject,
        "html": body_html,
    })
```

Modify `backend/src/api/scheduler.py`:

```python
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.api._check_in_lifecycle import get_or_create_pending_check_in
from src.db.models import Client
from src.lib.email import send_check_in_reminder_email


def _is_saturday_ist(today: date | None = None) -> bool:
    d = today if today is not None else datetime.now(ZoneInfo("Asia/Kolkata")).date()
    return d.weekday() == 5  # Monday=0 ... Saturday=5


async def _run_check_in_reminders(db) -> int:
    clients = (await db.execute(
        select(Client).where(
            Client.journey_stage != "completed",
            Client.user_id.is_not(None),
            Client.email.is_not(None),
        )
    )).scalars().all()

    sent = 0
    for client in clients:
        await get_or_create_pending_check_in(db, client.id, client.hc_user_id)
        send_check_in_reminder_email(
            to=client.email,
            client_name=client.full_name,
            portal_url=f"{get_settings().frontend_url}/me/checkins",
        )
        sent += 1
    await db.commit()
    return sent
```

And extend `run_scheduled_tasks`'s body (after the existing snippet-retirement block, before the `return`):

```python
    tasks_run = ["snippet_retirement"]
    if _is_saturday_ist():
        reminder_count = await _run_check_in_reminders(db)
        tasks_run.append("check_in_reminders")
        logger.info("scheduled_task_run", task="check_in_reminders", reminder_count=reminder_count)

    return SchedulerResult(tasks_run=tasks_run, retired_count=retired_count)
```

(Replace the existing hardcoded `tasks_run=["snippet_retirement"]` in the final `return` — it becomes the `tasks_run` list built above.)

Add the second cron trigger to `.github/workflows/scheduler.yml`:

```yaml
on:
  schedule:
    - cron: '0 1 * * *'   # 01:00 UTC = 06:30 IST, daily (existing — snippet retirement)
    - cron: '0 4 * * 6'   # 04:00 UTC = 09:30 IST, Saturdays only (check-in reminders)
  workflow_dispatch:
```

(No change needed to the job body — `run_scheduled_tasks` itself checks `_is_saturday_ist()` regardless of which cron fired it, so both trigger times safely hit the same endpoint. Note: the snippet-retirement task now runs twice on Saturdays — once from each cron. This is harmless since `_should_retire` is already idempotent, retiring an already-retired snippet is a no-op; not worth adding trigger-source detection to avoid.)

- [ ] **Step 5.6: Run — confirm pass**

Run: `cd backend && pytest tests/unit/test_scheduler.py tests/integration/test_scheduler.py -v`
Expected: all PASS

- [ ] **Step 5.7: Full backend suite — confirm no regressions**

Run: `cd backend && pytest -x`

- [ ] **Step 5.8: Commit**

```bash
git add backend/src/lib/email.py backend/src/api/scheduler.py .github/workflows/scheduler.yml backend/tests/unit/test_scheduler.py backend/tests/integration/test_scheduler.py
git commit -m "feat(check-ins): Saturday 9:30am IST reminder creates pending request + emails client (PHASE-02b Task 5)"
```

---

## Task 6: Frontend — client-facing check-in API wrappers

**Files:**
- Modify: `frontend/src/lib/api/me.ts` (add check-in functions)
- Modify: `frontend/src/lib/api/checkIns.ts` (add HC-side `requestCheckIn`)
- Test: `frontend/tests/unit/me-api.test.ts` (extend)

**Interfaces:**
- Produces: `listMyCheckIns(): Promise<{items: CheckInOut[]; next_cursor: string|null}>`, `submitMyCheckIn(payload: dict): Promise<CheckInOut>` in `me.ts`; `requestCheckIn(clientId: string): Promise<CheckInOut>` in `checkIns.ts` — Tasks 7 and 9 consume these.

- [ ] **Step 6.1: Write the failing tests**

Check `frontend/src/lib/api/checkIns.ts`'s existing `CheckInOutSchema` shape first (it needs `payload`/`requested_at` made nullable to match Task 2's backend change) — read the file before editing; extend its schema and add tests mirroring the pattern already used for `me-api.test.ts` (Task 3 of PHASE-02a) — one test per new function, asserting the exact URL/method/body, same style as that file's existing 3 tests. (Full test code omitted here for brevity of this already-long task — write it in the exact style of `frontend/tests/unit/me-api.test.ts`'s existing tests, one `it(...)` block per function, mocking `fetchWithAuth`.)

- [ ] **Step 6.2: Run — confirm failure**

Run: `cd frontend && npx vitest run tests/unit/me-api.test.ts tests/unit/checkIns-api.test.ts`

- [ ] **Step 6.3: Implement**

In `frontend/src/lib/api/checkIns.ts`, update `CheckInOutSchema` (currently declares `payload: z.record(z.string(), z.unknown())` non-nullable, no `requested_at` field):

```ts
export const CheckInOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  hc_user_id: z.string(),
  payload: z.record(z.string(), z.unknown()).nullable(),
  requested_at: z.string().nullable(),
  sentiment_flag: z.string().nullable(),
  created_at: z.string(),
});
```

Add to `checkIns.ts`:

```ts
export async function requestCheckIn(clientId: string): Promise<CheckInOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/check-ins/request`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Request check-in failed: ${res.status}`);
  return CheckInOutSchema.parse(await res.json());
}
```

Add to `frontend/src/lib/api/me.ts`:

```ts
import { CheckInOutSchema, type CheckInOut } from "@/lib/api/checkIns";

const PaginatedCheckInsSchema = z.object({
  items: z.array(CheckInOutSchema),
  next_cursor: z.string().nullable(),
});

export async function listMyCheckIns(): Promise<{ items: CheckInOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/check-ins`);
  if (!res.ok) throw new Error(`List my check-ins failed: ${res.status}`);
  return PaginatedCheckInsSchema.parse(await res.json());
}

export async function submitMyCheckIn(payload: Record<string, unknown>): Promise<CheckInOut> {
  const res = await fetchWithAuth(`${API_URL}/api/me/check-ins`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  });
  if (!res.ok) throw new Error(`Submit check-in failed: ${res.status}`);
  return CheckInOutSchema.parse(await res.json());
}
```

- [ ] **Step 6.4: Run — confirm pass**

Run: `cd frontend && npx vitest run`

- [ ] **Step 6.5: Commit**

```bash
git add frontend/src/lib/api/checkIns.ts frontend/src/lib/api/me.ts frontend/tests/unit/
git commit -m "feat(check-ins): frontend API wrappers for request/submit/list (PHASE-02b Task 6)"
```

---

## Task 7: Frontend — 2-tab Summary/Chat shell + `ChatTab` (Check-ins view) on client detail

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx`

**Interfaces:**
- Consumes: `requestCheckIn` (Task 6), `listClientCheckIns` (already exists, `checkIns.ts`).
- Produces: a `ChatTab` component within this file — PHASE-02c adds a Text sub-tab next to Check-ins inside it.

- [ ] **Step 7.1: Add tab state**

In `frontend/src/app/(app)/clients/[clientId]/page.tsx`, right after line 120 (`const [client, setClient] = useState<ClientDetailOut | null>(null);`):

```tsx
  const [activeTab, setActiveTab] = useState("summary");
```

- [ ] **Step 7.2: Add the Tabs import**

Add to the import block at the top of the file:

```tsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { listClientCheckIns, requestCheckIn, type CheckInOut } from "@/lib/api/checkIns";
```

- [ ] **Step 7.3: Wrap the existing Summary content — opening insertion**

Immediately after the `<>` fragment open (currently line 322, right before the `{/* Client header */}` comment), insert:

```tsx
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-8">
            <TabsList variant="line">
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="chat">Chat</TabsTrigger>
            </TabsList>
            <TabsContent value="summary" className="space-y-8">
```

Every line of existing content from the old `{/* Client header */}` comment through the end of the Details section (the ~660 lines currently between the old line 323 and line 984) is **unchanged** — only its indentation nesting level changes (it's now inside `<TabsContent value="summary">`), no JSX content itself is edited.

- [ ] **Step 7.4: Wrap the existing Summary content — closing insertion + new Chat tab**

Immediately before the fragment's closing `</>`  (currently line 985), insert:

```tsx
            </TabsContent>
            <TabsContent value="chat">
              <ChatTab clientId={clientId} />
            </TabsContent>
          </Tabs>
```

- [ ] **Step 7.5: Add the `ChatTab` component**

Add below the `export default function ClientDetailPage()` closing brace (matching this file's existing convention of colocating tab-content components in the same file, same pattern as `NotesTab` in `sessions/[sessionId]/page.tsx`):

```tsx
function ChatTab({ clientId }: { clientId: string }) {
  const [checkIns, setCheckIns] = useState<CheckInOut[] | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    listClientCheckIns(clientId).then((data) => setCheckIns(data.items)).catch(() => setCheckIns([]));
  }, [clientId]);

  const pending = checkIns?.find((c) => c.requested_at && c.payload === null) ?? null;

  async function handleRequest() {
    setRequesting(true);
    setRequestError(null);
    try {
      const created = await requestCheckIn(clientId);
      setCheckIns((prev) => [created, ...(prev ?? [])]);
    } catch {
      setRequestError("A check-in is already pending, or the request failed.");
    } finally {
      setRequesting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-bold text-foreground">Check-ins</h2>
        <button
          onClick={handleRequest}
          disabled={requesting || pending !== null}
          className="rounded-md border border-border px-3 py-1.5 font-sans text-xs font-bold uppercase tracking-widest text-foreground disabled:opacity-50"
        >
          {pending ? "Awaiting answer" : requesting ? "Requesting…" : "Request check-in"}
        </button>
      </div>

      {requestError && <p className="font-sans text-sm text-destructive">{requestError}</p>}

      {checkIns === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}

      {checkIns !== null && checkIns.filter((c) => c.payload !== null).length === 0 && (
        <p className="font-sans text-sm italic text-muted-foreground">No check-ins yet.</p>
      )}

      {checkIns !== null && (
        <ul className="space-y-3">
          {checkIns
            .filter((c) => c.payload !== null)
            .map((c) => (
              <li key={c.id} className="rounded-md border border-border p-4 font-sans text-sm">
                <p className="mb-1 text-xs text-muted-foreground">
                  {new Date(c.created_at).toLocaleDateString()}
                </p>
                <pre className="whitespace-pre-wrap font-sans text-sm">
                  {JSON.stringify(c.payload, null, 2)}
                </pre>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
```

(Raw JSON display for the payload is intentionally minimal for this first slice — a nicer per-metric rendering is easy follow-up polish once the metric list in Design Decision 4 is confirmed; not blocking this task.)

- [ ] **Step 7.5: E2E — extend `mockAuthAndApi` and add a test**

In `frontend/tests/e2e/fixtures/mock-api.ts`, extend the existing check-ins catch-all (currently `if (path.startsWith("/api/check-ins") ...)`) to also handle the new request route, and add to `core-cycle.spec.ts` (or a new small spec) a test clicking the "Chat" tab and the "Request check-in" button, asserting the button becomes "Awaiting answer".

- [ ] **Step 7.6: Run full frontend suite**

Run: `cd frontend && npx vitest run && npx playwright test`

- [ ] **Step 7.7: Commit**

```bash
git add "frontend/src/app/(app)/clients/[clientId]/page.tsx" frontend/tests/e2e/
git commit -m "feat(client-detail): 2-tab Summary/Chat shell with Check-ins view (PHASE-02b Task 7, D-20)"
```

---

## Task 8: Frontend — `/me/checkins` page (client-side)

**Files:**
- Create: `frontend/src/app/me/checkins/page.tsx`
- Modify: `frontend/src/app/me/layout.tsx` (add nav link)

**Interfaces:**
- Consumes: `listMyCheckIns`, `submitMyCheckIn` (Task 6).

- [ ] **Step 8.1: Add the nav link**

In `frontend/src/app/me/layout.tsx`, change the `<nav>` block to include a link (mirrors `(app)/layout.tsx`'s `NAV_LINKS` pattern, scaled down to what exists so far):

```tsx
        <nav className="mx-auto flex h-12 max-w-2xl items-center gap-4 px-4 sm:px-6">
          <Link href="/me" className="font-heading text-lg font-black text-foreground">
            Tapas
          </Link>
          <Link href="/me/checkins" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground">
            Check-ins
          </Link>
        </nav>
```

(Add `import Link from "next/link";` to the top of the file.)

- [ ] **Step 8.2: Implement the page**

```tsx
// frontend/src/app/me/checkins/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { listMyCheckIns, submitMyCheckIn } from "@/lib/api/me";
import type { CheckInOut } from "@/lib/api/checkIns";

const METRICS = [
  "Energy levels", "Sleep quality", "Diet adherence", "Stress levels", "Hydration",
  "Physical activity", "Mood", "Digestion", "Motivation", "Weight trend",
] as const;

export default function CheckInsPage() {
  const [checkIns, setCheckIns] = useState<CheckInOut[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listMyCheckIns().then((data) => setCheckIns(data.items)).catch(() => setCheckIns([]));
  }, []);

  const pending = checkIns?.find((c) => c.requested_at && c.payload === null) ?? null;

  function toggleMetric(metric: string) {
    setSelected((prev) => {
      if (prev.includes(metric)) return prev.filter((m) => m !== metric);
      if (prev.length >= 3) return prev;
      return [...prev, metric];
    });
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const metrics = Object.fromEntries(selected.map((m) => [m, ratings[m] ?? 5]));
      const updated = await submitMyCheckIn({ metrics, note: note || undefined });
      setCheckIns((prev) => [updated, ...(prev ?? []).filter((c) => c.id !== updated.id)]);
      setSelected([]);
      setRatings({});
      setNote("");
    } finally {
      setSubmitting(false);
    }
  }

  const answeredCheckIns = (checkIns ?? []).filter((c) => c.payload !== null);

  return (
    <div className="space-y-8">
      <h1 className="font-heading text-3xl font-black text-foreground">Check-ins</h1>

      {pending && (
        <div className="space-y-4 rounded-md border p-4">
          <p className="font-sans text-sm text-foreground">
            Your coach asked for a check-in. Pick 3 things to rate:
          </p>
          <div className="flex flex-wrap gap-2">
            {METRICS.map((m) => (
              <button
                key={m}
                onClick={() => toggleMetric(m)}
                className={`rounded-full border px-3 py-1 font-sans text-xs ${
                  selected.includes(m) ? "border-primary bg-primary text-primary-foreground" : "border-border text-foreground"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          {selected.map((m) => (
            <div key={m} className="flex items-center gap-3">
              <span className="w-40 font-sans text-sm">{m}</span>
              <input
                type="range" min={1} max={10}
                value={ratings[m] ?? 5}
                onChange={(e) => setRatings((prev) => ({ ...prev, [m]: Number(e.target.value) }))}
              />
              <span className="font-sans text-sm">{ratings[m] ?? 5}/10</span>
            </div>
          ))}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Anything else? (optional)"
            className="w-full rounded-md border border-border p-2 font-sans text-sm"
          />
          <Button onClick={handleSubmit} disabled={selected.length !== 3 || submitting}>
            {submitting ? "Submitting…" : "Submit check-in"}
          </Button>
        </div>
      )}

      {!pending && checkIns !== null && (
        <p className="font-sans text-sm text-muted-foreground">
          Nothing to answer right now — you can still check in any time from here.
        </p>
      )}

      <div className="space-y-3">
        <h2 className="font-heading text-lg font-bold text-foreground">Past check-ins</h2>
        {answeredCheckIns.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">None yet.</p>
        )}
        {answeredCheckIns.map((c) => (
          <div key={c.id} className="rounded-md border border-border p-4 font-sans text-sm">
            <p className="mb-1 text-xs text-muted-foreground">{new Date(c.created_at).toLocaleDateString()}</p>
            <pre className="whitespace-pre-wrap">{JSON.stringify(c.payload, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 8.3: E2E test**

Add to `frontend/tests/e2e/auth.spec.ts` or a new `checkins.spec.ts`: mock `/api/me/check-ins` GET returning one pending item and POST returning the answered version; visit `/me/checkins`; select 3 metrics; submit; assert the pending banner disappears and the answer shows under "Past check-ins".

- [ ] **Step 8.4: Run full suite**

Run: `cd frontend && npx vitest run && npx playwright test`

- [ ] **Step 8.5: Commit**

```bash
git add frontend/src/app/me/checkins/ frontend/src/app/me/layout.tsx frontend/tests/e2e/
git commit -m "feat(me): /me/checkins page — answer pending requests, see history (PHASE-02b Task 8)"
```

---

## Self-review

**Spec coverage:** D-21 (request/answer lifecycle) ✓, D-22 (10 fixed metrics, pick-3) ✓ — flagged for content confirmation, D-23 (Saturday 9:30am IST reminder via existing scheduled-task mechanism) ✓, D-20 (2-tab Summary/Chat shell) ✓ — first content only, Text/Logged Meals sub-views are PHASE-02c/PHASE-03. D-24 (Roster Board "what's new" passive indicator) is **not** in this plan — deferred to whichever of 02c/PHASE-03 ships last, since it needs to aggregate signals across Check-ins + Text + Meals and building a one-signal version now would need rework twice more. Flagged, not silently dropped.

**Placeholder scan:** No TBD/TODO. The raw-JSON payload rendering (Task 7/8) is a named, deliberate v1 simplification, not a placeholder — it's real, functional, just not the nicest presentation.

**Type consistency:** `CheckInOut` (backend Pydantic) ↔ `CheckInOutSchema` (frontend zod) both get `payload`/`requested_at` made nullable in the same task-pair (Task 2 backend, Task 6 frontend) — no drift window between them since both land before any consumer (Tasks 7/8) is built.

**Known follow-ups (not silently dropped):**
- The 10-metric list (Design Decision 4) needs SoJo's explicit confirmation — real product copy, not mine to finalize unilaterally.
- Roster Board D-24 indicator, as noted above.
- `_check_in_lifecycle.py`'s existence as a separate tiny module (rather than inlining in `check_ins.py`) is solely to dodge a circular import — flagged so a future reader isn't confused by the split.

**Execution:** Subagent-driven, per SoJo's standing instruction — no execution-choice question needed.
