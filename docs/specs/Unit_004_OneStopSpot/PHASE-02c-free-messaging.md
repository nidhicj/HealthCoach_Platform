# PHASE-02c — Free Messaging / Text View (D-25) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan builds directly on PHASE-02a (`/me/*` shell) and PHASE-02b (2-tab Summary/Chat shell + Check-ins view, `ChatTab` component) — both must be shipped first. Read PHASE-02b's `ChatTab` implementation before starting; do not re-implement it.

**Goal:** Either side (HC or client) can send a free-text message, optionally with one photo attachment, inside the Chat tab (HC side) / `/me/chat` (client side). Permanent once sent — no edit, no delete (D-25). When the HC replies, the client gets an email; when the client sends something, the HC gets no email (same passive-indicator philosophy as check-ins, D-24).

## Design decisions flagged for SoJo's review

1. **A genuine spec inconsistency, resolved in favor of the more recent decision.** `SPEC-0001-one-stop-spot.md`'s F5 section (WhatsApp, deferred) has a table titled "Email notification model for MVP" with a row: *"Client sends a free message → HC: 'Sunita sent you a message' + preview"*. This directly contradicts F2/D-24's own text: *"When the client sends something, the HC does **not** get emailed or pinged — same Roster Board indicator as check-ins (D-24)."* D-24 is the newer, more specific decision (2026-07-08, explicitly named "replaces" the older badge/email idea) — this plan follows **D-24**: client → HC message sends no email. Flagging this so SoJo can correct the stale F5 table row separately; not blocking this plan on it.
2. **Attachment scope: images only, not any file type.** The spec says "optional photo attachment" (singular, photo) — this plan restricts uploads to `image/jpeg`, `image/png`, `image/webp`, `image/heic` (common phone-camera formats), capped at 10 MB, distinct from the existing session-file-library's 25 MB/document-oriented allowlist (`backend/src/api/files.py`). If a use case for non-image attachments emerges later, that's a new allowlist entry, not a redesign.
3. **No signed-URL infrastructure exists in this codebase** (confirmed: `backend/src/lib/s3.py` has no presigned-URL function; the one place bytes are read back — `llm_service`'s `s3_get` — is server-side only, never served to a browser). This plan adds the **first-ever download-proxy endpoint** in this codebase (`GET .../messages/{id}/attachment`, both HC and client variants) rather than inventing signed-URL generation from scratch — smaller, consistent with how uploads already work here (backend-mediated, not direct-to-storage).

**Architecture:** One new table (`client_messages`), one new backend module (`backend/src/api/messages.py`, HC-side — mirrors the existing `check_ins.py`/`me.py` split exactly: HC-facing routes live in their own file, client-facing routes are added to the already-existing `me.py`), one new S3 key-builder function, two new email-adjacent pieces (one email template, zero for the other direction per Decision 1). Frontend: `ChatTab` (PHASE-02b) gains an inner Text/Check-ins tab switcher; `/me/chat` is a new page mirroring the client side.

**Tech stack:** Same as PHASE-02a/02b. No new dependency — multipart upload uses FastAPI's existing `UploadFile`/`Form`, exactly like `files.py` already does.

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before backend commands
- Backend tests hit a real PostgreSQL DB — no DB mocking; mock `s3_put`/`s3_get` exactly as `test_file_upload.py` already does (`patch("src.api.messages.s3_put", new_callable=AsyncMock)`)
- After the migration, run `alembic upgrade head` against `tapas_dev` too, not just `tapas_test`
- Messages are immutable once sent — no PATCH/DELETE endpoint of any kind in this plan, matching D-25 exactly
- Every API module in this codebase defines its own private `_get_owned_client` helper rather than importing a shared one (confirmed convention: `clients.py`, `supplements.py`, `diet_charts.py` each have their own identical copy) — `messages.py` follows the same convention, don't refactor this into a shared helper as part of this plan

---

## Task 1: `client_messages` table + model

**Files:**
- Create: `backend/alembic/versions/<new_revision>_add_client_messages_table.py`
- Modify: `backend/src/db/models/coaching.py` (add `ClientMessage`, update module docstring)

**Interfaces:**
- Produces: `ClientMessage(id, client_id, hc_user_id, direction, body, attachment_storage_path, attachment_original_filename, attachment_mime_type, sent_at)` — every task below consumes this model.

- [x] **Step 1.1: Check current migration head**

Run: `cd backend && alembic heads` — confirm the current head (should be PHASE-02b's `add_requested_at_to_check_ins` revision) before generating a new one so it chains correctly.

- [x] **Step 1.2: Generate and write the migration**

Run: `cd backend && alembic revision -m "add_client_messages_table"`

```python
"""add_client_messages_table

Revision ID: <generated>
Revises: <PHASE-02b's revision id>
Create Date: <generated>
"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "<PHASE-02b's revision id>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_messages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hc_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("direction", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachment_storage_path", sa.Text, nullable=True),
        sa.Column("attachment_original_filename", sa.Text, nullable=True),
        sa.Column("attachment_mime_type", sa.Text, nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("direction IN ('client', 'coach')", name="ck_client_messages_direction"),
    )
    op.create_index("idx_client_messages_client_sent", "client_messages", ["client_id", "sent_at"])


def downgrade() -> None:
    op.drop_index("idx_client_messages_client_sent", table_name="client_messages")
    op.drop_table("client_messages")
```

- [x] **Step 1.3: Add the model**

In `backend/src/db/models/coaching.py`, update the module docstring to `"""moms, briefs, action_items, check_ins, client_messages — the core coaching cycle tables."""` and add:

```python
class ClientMessage(Base):
    __tablename__ = "client_messages"
    __table_args__ = (Index("idx_client_messages_client_sent", "client_id", "sent_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_storage_path: Mapped[str | None] = mapped_column(Text)
    attachment_original_filename: Mapped[str | None] = mapped_column(Text)
    attachment_mime_type: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
```

Add `ClientMessage` to `backend/src/db/models/__init__.py`'s exports (check the existing pattern — every model in `coaching.py` is re-exported there).

- [x] **Step 1.4: Run — apply and verify**

```bash
cd backend && alembic upgrade head
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/tapas_dev alembic upgrade head
```

- [x] **Step 1.5: Commit**

```bash
git add backend/alembic/versions/ backend/src/db/models/coaching.py backend/src/db/models/__init__.py
git commit -m "feat(messages): client_messages table + model (PHASE-02c Task 1)"
```

---

## Task 2: S3 key-builder for message attachments

**Files:**
- Modify: `backend/src/lib/s3.py`
- Test: `backend/tests/unit/test_s3.py` (extend — check the file exists first; the fork research found `s3.py`'s existing unit tests but not this exact filename, confirm before assuming)

**Interfaces:**
- Produces: `build_message_attachment_key(client_id: UUID, message_id: UUID, filename: str) -> str` — Task 3 consumes this.

- [x] **Step 2.1: Write the failing test**

```python
def test_build_message_attachment_key_structure():
    from src.lib.s3 import build_message_attachment_key
    import uuid
    client_id = uuid.uuid4()
    message_id = uuid.uuid4()
    key = build_message_attachment_key(client_id, message_id, "photo.jpg")
    assert key == f"client-{client_id}/messages/{message_id}/photo.jpg"


def test_build_message_attachment_key_sanitizes_filename():
    from src.lib.s3 import build_message_attachment_key
    import uuid
    key = build_message_attachment_key(uuid.uuid4(), uuid.uuid4(), "my photo (1)!.jpg")
    assert " " not in key and "(" not in key and "!" not in key
```

- [x] **Step 2.2: Run — confirm failure**

Run: `cd backend && pytest tests/unit/test_s3.py -k message_attachment -v`

- [x] **Step 2.3: Implement**

Add to `backend/src/lib/s3.py`:

```python
def build_message_attachment_key(client_id: UUID, message_id: UUID, filename: str) -> str:
    """Returns R2 key: client-{client_id}/messages/{message_id}/{sanitized_filename}"""
    sanitized_file = _sanitize(filename, max_len=200)
    return f"client-{client_id}/messages/{message_id}/{sanitized_file}"
```

- [x] **Step 2.4: Run — confirm pass**

Run: `cd backend && pytest tests/unit/test_s3.py -v`

- [x] **Step 2.5: Commit**

```bash
git add backend/src/lib/s3.py backend/tests/unit/test_s3.py
git commit -m "feat(messages): S3 key-builder for message attachments (PHASE-02c Task 2)"
```

---

## Task 3: HC-side send + list — `backend/src/api/messages.py`

**Files:**
- Create: `backend/src/api/messages.py`
- Modify: `backend/src/lib/email.py` (add `send_message_notification_email`)
- Modify: `backend/src/main.py` (or wherever routers are registered — check `check_ins.py`'s registration point and mirror it)
- Test: `backend/tests/integration/test_messages.py` (new)

**Interfaces:**
- Produces: `MessageOut{id, client_id, hc_user_id, direction, body, has_attachment, attachment_original_filename, attachment_mime_type, sent_at}`, `POST /api/clients/{client_id}/messages`, `GET /api/clients/{client_id}/messages` — Task 5 (client-side) imports `MessageOut` from here, exactly like `me.py` already imports `CheckInOut` from `check_ins.py`.

- [x] **Step 3.1: Write the failing tests**

```python
# backend/tests/integration/test_messages.py
from unittest.mock import AsyncMock, patch

import pytest


async def _make_client(http_client, headers) -> dict:
    import uuid
    r = await http_client.post("/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_hc_can_send_text_only_message(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        data={"body": "How's the new routine going?"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["direction"] == "coach"
    assert body["body"] == "How's the new routine going?"
    assert body["has_attachment"] is False


@pytest.mark.asyncio
async def test_hc_send_message_with_attachment(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    with patch("src.api.messages.s3_put", new_callable=AsyncMock) as mock_put:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Here's a reference photo"},
            files={"attachment": ("ref.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201, r.text
    assert r.json()["has_attachment"] is True
    assert r.json()["attachment_original_filename"] == "ref.jpg"
    mock_put.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_rejects_non_image_attachment(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        data={"body": "doc"},
        files={"attachment": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_hc_reply_emails_client_when_email_on_record(http_client, hc_headers, db):
    import sqlalchemy as sa
    from src.db.models import Client
    client = await _make_client(http_client, hc_headers)
    row = (await db.execute(sa.select(Client).where(Client.id == client["id"]))).scalar_one()
    row.email = "client@example.com"
    await db.flush()
    await db.commit()

    with patch("src.api.messages.send_message_notification_email") as mock_email:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Great progress this week!"},
        )
    assert r.status_code == 201
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_hc_reply_skips_email_when_client_has_no_email(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    with patch("src.api.messages.send_message_notification_email") as mock_email:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Hi there"},
        )
    assert r.status_code == 201
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_list_client_messages_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/messages", headers=hc2_headers)
    assert r.status_code == 404
```

- [x] **Step 3.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_messages.py -v`
Expected: FAIL — module/routes don't exist

- [x] **Step 3.3: Implement**

Add to `backend/src/lib/email.py`:

```python
def send_message_notification_email(*, to: str, client_name: str, coach_name: str, preview: str, portal_url: str) -> None:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("resend_api_key not configured")

    resend.api_key = api_key

    safe_client = html.escape(client_name)
    safe_preview = html.escape(preview[:200])
    subject = f"Your coach replied — {coach_name}"
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
    <p style="font-size: 15px; white-space: pre-line;">{safe_preview}</p>
    <p style="margin: 24px 0;">
      <a href="{portal_url}" style="background: #5C6652; color: #F7F4EE; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">Open chat</a>
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

Create `backend/src/api/messages.py`:

```python
"""HC-side client_messages endpoints. Client-side counterpart lives in me.py."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, computed_field
from sqlalchemy import and_, or_, select

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.config import get_settings
from src.db.models import Client, ClientMessage
from src.lib.email import send_message_notification_email
from src.lib.s3 import build_message_attachment_key, s3_get, s3_put

router = APIRouter(tags=["messages"])

ALLOWED_ATTACHMENT_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ── schemas ────────────────────────────────────────────────────────────────────


class MessageOut(BaseModel):
    id: UUID
    client_id: UUID
    hc_user_id: UUID
    direction: str
    body: str
    attachment_original_filename: str | None
    attachment_mime_type: str | None
    sent_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def has_attachment(self) -> bool:
        return self.attachment_original_filename is not None


# ── shared helper (this module's own copy — see Global Constraints) ────────────


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# ── routes ─────────────────────────────────────────────────────────────────────


@router.post("/api/clients/{client_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_client_message(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    body: str = Form(...),
    attachment: UploadFile | None = None,
) -> MessageOut:
    client = await _get_owned_client(db, client_id, hc_id)

    msg = ClientMessage(client_id=client_id, hc_user_id=UUID(hc_id), direction="coach", body=body)

    if attachment is not None:
        if not attachment.content_type or attachment.content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type. Allowed: {sorted(ALLOWED_ATTACHMENT_MIME_TYPES)}",
            )
        content = await attachment.read()
        if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Attachment exceeds the 10 MB limit")

        db.add(msg)
        await db.flush()  # need msg.id for the storage key
        key = build_message_attachment_key(client_id, msg.id, attachment.filename or "unnamed")
        await s3_put(key, content, attachment.content_type)
        msg.attachment_storage_path = key
        msg.attachment_original_filename = attachment.filename or "unnamed"
        msg.attachment_mime_type = attachment.content_type
    else:
        db.add(msg)
        await db.flush()

    await db.commit()
    await db.refresh(msg)

    if client.email:
        send_message_notification_email(
            to=client.email,
            client_name=client.full_name,
            coach_name=claims.sub,  # HC's own display name isn't on TokenClaims; acceptable for v1, see Self-review
            preview=body[:200],
            portal_url=f"{get_settings().frontend_url}/me/chat",
        )

    return MessageOut.model_validate(msg)


@router.get("/api/clients/{client_id}/messages")
async def list_client_messages(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: str | None = None,
) -> PaginatedList[MessageOut]:
    await _get_owned_client(db, client_id, hc_id)

    q = select(ClientMessage).where(ClientMessage.client_id == client_id)
    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                ClientMessage.sent_at < cur_ts,
                and_(ClientMessage.sent_at == cur_ts, ClientMessage.id < cur_id),
            )
        )
    q = q.order_by(ClientMessage.sent_at.desc(), ClientMessage.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].sent_at, rows[-1].id)

    return PaginatedList(items=[MessageOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/api/clients/{client_id}/messages/{message_id}/attachment")
async def get_client_message_attachment(
    client_id: UUID,
    message_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> Response:
    await _get_owned_client(db, client_id, hc_id)
    msg = (await db.execute(
        select(ClientMessage).where(ClientMessage.id == message_id, ClientMessage.client_id == client_id)
    )).scalar_one_or_none()
    if msg is None or msg.attachment_storage_path is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    content = await s3_get(msg.attachment_storage_path)
    return Response(
        content=content,
        media_type=msg.attachment_mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{msg.attachment_original_filename}"'},
    )
```

Register the router — find where `check_ins.router` is included (likely `backend/src/main.py`) and add `messages.router` the same way.

- [x] **Step 3.4: Run — confirm pass**

Run: `cd backend && pytest tests/integration/test_messages.py -v`

- [x] **Step 3.5: Full backend suite**

Run: `cd backend && pytest -x`

- [x] **Step 3.6: Commit**

```bash
git add backend/src/api/messages.py backend/src/lib/email.py backend/src/main.py backend/tests/integration/test_messages.py
git commit -m "feat(messages): HC-side send/list/attachment-download + reply email (PHASE-02c Task 3)"
```

---

## Task 4: Client-side send/list/attachment — extend `me.py`

**Files:**
- Modify: `backend/src/api/me.py`
- Test: `backend/tests/integration/test_me.py` (extend)

**Interfaces:**
- Consumes: `MessageOut` from `src.api.messages` (Task 3), same import pattern as the existing `from src.api.check_ins import CheckInOut`.
- Produces: `POST /api/me/messages`, `GET /api/me/messages`, `GET /api/me/messages/{id}/attachment`.

- [x] **Step 4.1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_client_can_send_message(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/messages", headers=client_headers,
        data={"body": "Quick question about my meal plan"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["direction"] == "client"


@pytest.mark.asyncio
async def test_client_message_does_not_trigger_hc_email(http_client, client_headers, client_rec):
    from unittest.mock import patch
    with patch("src.api.me.send_message_notification_email") as mock_email:
        r = await http_client.post(
            "/api/me/messages", headers=client_headers,
            data={"body": "hi"},
        )
    assert r.status_code == 201
    mock_email.assert_not_called()  # D-24: HC never gets emailed for a client message


@pytest.mark.asyncio
async def test_client_lists_own_messages(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(
        f"/api/clients/{client_rec.id}/messages", headers=hc_headers, data={"body": "From your coach"},
    )
    await http_client.post("/api/me/messages", headers=client_headers, data={"body": "From me"})

    r = await http_client.get("/api/me/messages", headers=client_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


@pytest.mark.asyncio
async def test_client_cannot_list_other_clients_messages(http_client, hc_headers, client_headers, db):
    other = (await http_client.post("/api/clients", headers=hc_headers, json={"full_name": "Other"})).json()
    await http_client.post(f"/api/clients/{other['id']}/messages", headers=hc_headers, data={"body": "not yours"})

    r = await http_client.get("/api/me/messages", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []
```

- [x] **Step 4.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_me.py -k message -v`

- [x] **Step 4.3: Implement**

Add to the imports at the top of `backend/src/api/me.py`:

```python
from fastapi import Form, Response, UploadFile
from src.api.messages import ALLOWED_ATTACHMENT_MIME_TYPES, MAX_ATTACHMENT_SIZE_BYTES, MessageOut
from src.db.models import ClientMessage
from src.lib.s3 import build_message_attachment_key, s3_get, s3_put
```

Add the routes (note: this endpoint deliberately does **not** import or call `send_message_notification_email` — matches D-24, verified by Task 4's second test):

```python
@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def submit_my_message(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    body: str = Form(...),
    attachment: UploadFile | None = None,
) -> MessageOut:
    client = await _resolve_client(db, claims, hc_id)

    msg = ClientMessage(client_id=client.id, hc_user_id=UUID(hc_id), direction="client", body=body)

    if attachment is not None:
        if not attachment.content_type or attachment.content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type. Allowed: {sorted(ALLOWED_ATTACHMENT_MIME_TYPES)}",
            )
        content = await attachment.read()
        if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Attachment exceeds the 10 MB limit")

        db.add(msg)
        await db.flush()
        key = build_message_attachment_key(client.id, msg.id, attachment.filename or "unnamed")
        await s3_put(key, content, attachment.content_type)
        msg.attachment_storage_path = key
        msg.attachment_original_filename = attachment.filename or "unnamed"
        msg.attachment_mime_type = attachment.content_type
    else:
        db.add(msg)
        await db.flush()

    await db.commit()
    await db.refresh(msg)
    return MessageOut.model_validate(msg)


@router.get("/messages")
async def list_my_messages(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[MessageOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(ClientMessage).where(ClientMessage.client_id == client.id)
    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                ClientMessage.sent_at < cur_ts,
                and_(ClientMessage.sent_at == cur_ts, ClientMessage.id < cur_id),
            )
        )
    q = q.order_by(ClientMessage.sent_at.desc(), ClientMessage.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].sent_at, rows[-1].id)

    return PaginatedList(items=[MessageOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/messages/{message_id}/attachment")
async def get_my_message_attachment(
    message_id: UUID,
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> Response:
    client = await _resolve_client(db, claims, hc_id)
    msg = (await db.execute(
        select(ClientMessage).where(ClientMessage.id == message_id, ClientMessage.client_id == client.id)
    )).scalar_one_or_none()
    if msg is None or msg.attachment_storage_path is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    content = await s3_get(msg.attachment_storage_path)
    return Response(
        content=content,
        media_type=msg.attachment_mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{msg.attachment_original_filename}"'},
    )
```

- [x] **Step 4.4: Run — confirm pass, then full suite**

Run: `cd backend && pytest tests/integration/test_me.py -v && pytest -x`

- [x] **Step 4.5: Commit**

```bash
git add backend/src/api/me.py backend/tests/integration/test_me.py
git commit -m "feat(me): client-side send/list/attachment endpoints, no HC email on client message (PHASE-02c Task 4, D-24)"
```

---

## Task 5: Frontend — HC-side `messages.ts` + Text sub-tab inside `ChatTab`

**Files:**
- Create: `frontend/src/lib/api/messages.ts`
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx` (`ChatTab`, added in PHASE-02b Task 7)

**Interfaces:**
- Produces: `listClientMessages(clientId)`, `sendClientMessage(clientId, {body, attachment?})` — this task's own `ChatTab` update consumes them.

- [x] **Step 5.1: `frontend/src/lib/api/messages.ts`**

```ts
import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

export const MessageOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  hc_user_id: z.string(),
  direction: z.enum(["client", "coach"]),
  body: z.string(),
  has_attachment: z.boolean(),
  attachment_original_filename: z.string().nullable(),
  attachment_mime_type: z.string().nullable(),
  sent_at: z.string(),
});

export type MessageOut = z.infer<typeof MessageOutSchema>;

const PaginatedMessagesSchema = z.object({
  items: z.array(MessageOutSchema),
  next_cursor: z.string().nullable(),
});

export async function listClientMessages(clientId: string): Promise<{ items: MessageOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/messages`);
  if (!res.ok) throw new Error(`List messages failed: ${res.status}`);
  return PaginatedMessagesSchema.parse(await res.json());
}

export async function sendClientMessage(
  clientId: string,
  input: { body: string; attachment?: File },
): Promise<MessageOut> {
  const form = new FormData();
  form.append("body", input.body);
  if (input.attachment) form.append("attachment", input.attachment);

  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/messages`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Send message failed: ${res.status}`);
  return MessageOutSchema.parse(await res.json());
}

export function messageAttachmentUrl(clientId: string, messageId: string): string {
  return `${API_URL}/api/clients/${clientId}/messages/${messageId}/attachment`;
}
```

- [x] **Step 5.2: Give `ChatTab` an inner Text/Check-ins switcher**

In `frontend/src/app/(app)/clients/[clientId]/page.tsx`, modify `ChatTab` (added in PHASE-02b) to add its own nested tab state and a `TextView` sub-component. Replace `ChatTab`'s current body (everything from `return (` onward) with:

```tsx
function ChatTab({ clientId }: { clientId: string }) {
  const [subTab, setSubTab] = useState("text");
  // ...existing checkIns/requesting/requestError state from PHASE-02b stays exactly as-is...

  return (
    <div className="space-y-6">
      <Tabs value={subTab} onValueChange={setSubTab}>
        <TabsList variant="line">
          <TabsTrigger value="text">Text</TabsTrigger>
          <TabsTrigger value="checkins">Check-ins</TabsTrigger>
        </TabsList>
        <TabsContent value="text">
          <TextView clientId={clientId} />
        </TabsContent>
        <TabsContent value="checkins">
          {/* PHASE-02b's existing Check-ins JSX (request button, pending banner, list) moves here unchanged */}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TextView({ clientId }: { clientId: string }) {
  const [messages, setMessages] = useState<MessageOut[] | null>(null);
  const [body, setBody] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    listClientMessages(clientId).then((data) => setMessages(data.items.slice().reverse())).catch(() => setMessages([]));
  }, [clientId]);

  async function handleSend() {
    if (!body.trim()) return;
    setSending(true);
    try {
      const sent = await sendClientMessage(clientId, { body, attachment: attachment ?? undefined });
      setMessages((prev) => [...(prev ?? []), sent]);
      setBody("");
      setAttachment(null);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="max-h-96 space-y-3 overflow-y-auto">
        {messages === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}
        {messages !== null && messages.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">No messages yet.</p>
        )}
        {messages?.map((m) => (
          <div
            key={m.id}
            className={`max-w-[75%] rounded-md border p-3 font-sans text-sm ${
              m.direction === "coach" ? "ml-auto border-primary/30 bg-primary/5" : "border-border"
            }`}
          >
            <p>{m.body}</p>
            {m.has_attachment && (
              <img
                src={messageAttachmentUrl(clientId, m.id)}
                alt={m.attachment_original_filename ?? "attachment"}
                className="mt-2 max-h-48 rounded"
              />
            )}
            <p className="mt-1 text-xs text-muted-foreground">{new Date(m.sent_at).toLocaleString()}</p>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text" value={body} onChange={(e) => setBody(e.target.value)}
          placeholder="Type a message…"
          className="flex-1 rounded-md border border-border px-3 py-2 font-sans text-sm"
        />
        <input
          type="file" accept="image/jpeg,image/png,image/webp,image/heic"
          onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
          className="w-40 font-sans text-xs"
        />
        <Button onClick={handleSend} disabled={sending || !body.trim()}>
          {sending ? "Sending…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
```

Add the new imports to this file's top-level import block:

```tsx
import { listClientMessages, sendClientMessage, messageAttachmentUrl, type MessageOut } from "@/lib/api/messages";
import { Button } from "@/components/ui/button";
```

- [x] **Step 5.3: E2E — extend mocks + add a test**

Extend `frontend/tests/e2e/fixtures/mock-api.ts` with `/api/clients/{id}/messages` GET/POST handlers; add a test to `core-cycle.spec.ts` (or a new spec) sending a text-only message from the Chat tab and asserting it appears in the thread.

- [x] **Step 5.4: Run full frontend suite**

Run: `cd frontend && npx vitest run && npx playwright test`

- [x] **Step 5.5: Commit**

```bash
git add frontend/src/lib/api/messages.ts "frontend/src/app/(app)/clients/[clientId]/page.tsx" frontend/tests/e2e/
git commit -m "feat(client-detail): Text sub-view inside Chat tab, HC side (PHASE-02c Task 5)"
```

---

## Task 6: Frontend — `/me/chat` page (client-side)

**Files:**
- Modify: `frontend/src/lib/api/me.ts` (add message wrappers)
- Create: `frontend/src/app/me/chat/page.tsx`
- Modify: `frontend/src/app/me/layout.tsx` (add nav link)

**Interfaces:**
- Consumes: `MessageOutSchema`/`MessageOut` from `@/lib/api/messages` (Task 5), reusing rather than redefining, same pattern as `me.ts` already reuses `ActionItemOutSchema`/`CheckInOutSchema`.

- [x] **Step 6.1: Add wrappers to `frontend/src/lib/api/me.ts`**

```ts
import { MessageOutSchema, type MessageOut } from "@/lib/api/messages";

const PaginatedMessagesSchema = z.object({
  items: z.array(MessageOutSchema),
  next_cursor: z.string().nullable(),
});

export async function listMyMessages(): Promise<{ items: MessageOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/messages`);
  if (!res.ok) throw new Error(`List my messages failed: ${res.status}`);
  return PaginatedMessagesSchema.parse(await res.json());
}

export async function sendMyMessage(input: { body: string; attachment?: File }): Promise<MessageOut> {
  const form = new FormData();
  form.append("body", input.body);
  if (input.attachment) form.append("attachment", input.attachment);

  const res = await fetchWithAuth(`${API_URL}/api/me/messages`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Send message failed: ${res.status}`);
  return MessageOutSchema.parse(await res.json());
}

export function myMessageAttachmentUrl(messageId: string): string {
  return `${API_URL}/api/me/messages/${messageId}/attachment`;
}
```

- [x] **Step 6.2: Add the nav link**

In `frontend/src/app/me/layout.tsx`, add next to the existing `/me/checkins` link (PHASE-02b Task 8):

```tsx
          <Link href="/me/chat" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground">
            Chat
          </Link>
```

- [x] **Step 6.3: Implement the page**

```tsx
// frontend/src/app/me/chat/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { listMyMessages, sendMyMessage, myMessageAttachmentUrl } from "@/lib/api/me";
import type { MessageOut } from "@/lib/api/messages";

export default function ChatPage() {
  const [messages, setMessages] = useState<MessageOut[] | null>(null);
  const [body, setBody] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    listMyMessages().then((data) => setMessages(data.items.slice().reverse())).catch(() => setMessages([]));
  }, []);

  async function handleSend() {
    if (!body.trim()) return;
    setSending(true);
    try {
      const sent = await sendMyMessage({ body, attachment: attachment ?? undefined });
      setMessages((prev) => [...(prev ?? []), sent]);
      setBody("");
      setAttachment(null);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-3xl font-black text-foreground">Chat</h1>

      <div className="max-h-[60vh] space-y-3 overflow-y-auto">
        {messages === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}
        {messages !== null && messages.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">No messages yet — say hello!</p>
        )}
        {messages?.map((m) => (
          <div
            key={m.id}
            className={`max-w-[85%] rounded-md border p-3 font-sans text-sm ${
              m.direction === "client" ? "ml-auto border-primary/30 bg-primary/5" : "border-border"
            }`}
          >
            <p>{m.body}</p>
            {m.has_attachment && (
              <img
                src={myMessageAttachmentUrl(m.id)}
                alt={m.attachment_original_filename ?? "attachment"}
                className="mt-2 max-h-48 rounded"
              />
            )}
            <p className="mt-1 text-xs text-muted-foreground">{new Date(m.sent_at).toLocaleString()}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="text" value={body} onChange={(e) => setBody(e.target.value)}
          placeholder="Type a message…"
          className="flex-1 rounded-md border border-border px-3 py-2 font-sans text-sm"
        />
        <input
          type="file" accept="image/jpeg,image/png,image/webp,image/heic"
          onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
          className="w-32 font-sans text-xs"
        />
        <Button onClick={handleSend} disabled={sending || !body.trim()}>
          {sending ? "Sending…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
```

- [x] **Step 6.4: E2E test**

Add a test mocking `/api/me/messages` GET/POST, visiting `/me/chat`, sending a message, asserting it appears in the thread.

- [x] **Step 6.5: Run full suite, then commit**

```bash
cd frontend && npx vitest run && npx playwright test
git add frontend/src/lib/api/me.ts frontend/src/app/me/chat/ frontend/src/app/me/layout.tsx frontend/tests/e2e/
git commit -m "feat(me): /me/chat page — send/receive messages with photo attachments (PHASE-02c Task 6)"
```

---

## Self-review

**Spec coverage:** D-25 (free messaging, permanent, no edit/delete) ✓. Email direction matches D-24 exactly (HC replies → client emailed; client sends → no HC email) — Decision 1 above documents and resolves the F5-table contradiction rather than silently picking a side.

**Placeholder scan:** No TBD/TODO. `coach_name=claims.sub` in Task 3's email call is a real, working value (the HC's user id, not their display name — `TokenClaims` has no display-name field) — flagged below as a naming quality gap, not a stub.

**Type consistency:** `MessageOut` defined once in `messages.py` (Task 3), imported by `me.py` (Task 4) exactly like the existing `CheckInOut`/`ActionItemOut` cross-imports — no duplicate schema definition anywhere. Frontend `MessageOutSchema` (Task 5) is the single source the client-side wrappers (Task 6) import, not redefined.

**Known follow-ups (not silently dropped):**
- Task 3's reply email uses `claims.sub` (a UUID) where "coach name" should ideally be the HC's actual display name. Fixing this requires a DB lookup (`User.display_name`) inside the endpoint — small, real, but adds a query this plan didn't scope; do it as a 1-line follow-up when this ships, or fold it in during review if preferred.
- No read receipts / unread counts — matches spec exactly ("no read_at... messages are permanent once sent"), not an oversight.
- Roster Board D-24 "what's new" indicator still not built (same note as PHASE-02b's self-review) — this is now the second of three signal sources (Check-ins, Text) to exist; PHASE-03 (Logged Meals) will be the third, and that's the natural point to build the aggregated indicator once, rather than three separate partial versions.

**Execution:** Subagent-driven, per SoJo's standing instruction.

---

## Shipped (2026-08-19)

All 6 tasks complete, individually reviewed (with fix rounds where findings surfaced), plus a
final whole-plan review that caught cross-task seam defects no single task's reviewer could see.
Commits `3b7cecd..3e6d950` (tasks) then `8a4aa9e..e40f951` (final-review fix wave) on
`feature/unit-004-one-stop-spot` (not pushed). Full backend suite: 378/378 passing. Frontend
vitest: 134/134 passing (18 files). `tsc --noEmit`: zero new errors.

**Real bugs found and fixed during task review, not caught by any test written against this
plan's own code samples:**
- **Task 3**: reply-notification email's `coach_name` shipped the HC's raw UUID (`claims.sub`)
  instead of their display name — fixed to query `User.display_name` with a fallback.
- **Task 3**: the attachment-download endpoint and the list endpoint's ordering/pagination had
  zero test coverage as originally written — added.
- **Task 3**: `body` had no `min_length` guard, allowing empty-string messages — added, matching
  an existing codebase precedent (`supplements.py`).
- **Task 4**: the "client message doesn't email the HC" (D-24) regression test patched the wrong
  target (`src.lib.email.send_message_notification_email` at its definition site) — would not
  have caught the realistic regression (a future `from src.lib.email import ...` added to
  `me.py`). Replaced with a structural assertion that the name is never bound in that module.
- **Task 5**: `TextView.handleSend` had no error handling — a failed send silently reverted the
  button with zero feedback. Fixed to mirror the sibling Check-ins error pattern already in the
  same file; carried forward into Task 6 from the start.

**Whole-plan final review** (`opus`, base `0b04f5b`, head `3e6d950`) independently re-verified
D-24 and D-25 compliance repo-wide (not just per-task), confirmed the HC-side and client-side
implementations hadn't drifted from each other, and found one Critical + 4 additional Important
defects living precisely in the seam between the backend tasks (3/4) and frontend tasks (5/6) —
exactly the class of bug no single task's own reviewer could see:
- **Critical**: attachment images never rendered in a real browser — both `<img src=...>` call
  sites pointed at Bearer-token-protected endpoints, but a browser `<img>` GET can't carry an
  Authorization header, and this app's access token lives only in module memory (ADR-0005 §5,
  no cookie fallback). Fixed with a shared `AuthedImage` component (`fetchWithAuth` → blob URL).
- The reply-notification email call was unwrapped; combined with D-25's immutability, a Resend
  outage would have turned a successful send into a 500 + retry + permanent duplicate message.
  Fixed to mirror `check_ins.py`'s existing try/except convention.
- Non-Latin-1 filenames (e.g. Devanagari, common for phone-camera uploads from Indian users)
  500'd both attachment-download endpoints — `Content-Disposition` was built from the raw,
  unsanitized filename against Starlette's latin-1 header encoding. Fixed with RFC 5987 encoding
  in both `messages.py` and `me.py`.
- The client-facing upload endpoint (`me.py`) read the full attachment into memory before
  checking its size. Fixed to check `UploadFile.size` (verified against Starlette's own source
  to confirm it's populated before the handler runs) before reading, in both files.
- All 3 new e2e tests for messaging were dead-on-arrival due to a pre-existing, environment-wide
  BFF-proxy/mock-interception gap (unrelated to this plan, confirmed by an independent reviewer
  via commit ancestry and cross-spec grep) — leaving `/me/chat` with zero working automated
  coverage. Marked the 3 tests `test.fixme()` with an explanatory comment, and added
  `MeChatPage.test.tsx` as real, working coverage in the meantime.

None of the above block this phase's own scope; all are logged in `.superpowers/sdd/PHASE-02c-free-messaging/progress.md`.

**Not yet fixed — flagged as follow-ups, not blocking:**
- `quote(filename)` in the RFC 5987 fix omits `safe=""`, so a literal `/` in a filename is left
  unescaped — non-strict-RFC-compliant but not exploitable (all other bytes including CR/LF/
  quotes are still escaped); mainstream browsers tolerate it. Worth a follow-up ticket if strict
  compliance ever matters.
- The pre-existing PHASE-02b check-in e2e test in `core-cycle.spec.ts` likely shares the same
  BFF-proxy interception bug as the 3 fixme'd tests above, but was left untouched — out of this
  review's scope, a live gap for a future pass.
- `next_cursor` is returned by both list endpoints but consumed by neither UI — with >20
  messages, both sides silently show only the newest 20 with no "load older" affordance.
- No structured logging on message send/attachment-upload/download (`files.py` has this
  pattern; `messages.py`/`me.py` don't yet).
- Message attachments in R2 have no deletion path yet — a second class of orphan-able object
  the eventual DPDP erasure job (principle 8, "deletion is real") will need to cover.
- **The stale `SPEC-0001-one-stop-spot.md` F5 table row** ("Client sends a free message → HC:
  'Sunita sent you a message' + preview") still contradicts this plan's own D-24 (client sends
  no HC email) — flagged in this plan's Decision 1 as deferred to SoJo, not resolved here.
