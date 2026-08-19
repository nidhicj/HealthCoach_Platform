# PHASE-03 — Logged Meals (F3, D-26) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Dependency — read before starting, this is a real risk, not a formality.** F3 lives "inside the Chat tab's Logged Meals view" (`SPEC-0001-one-stop-spot.md` F3, D-20). That Chat tab (`ChatTab` component, 2-tab Summary/Chat client-detail shell) is being introduced by **PHASE-02b** and extended by **PHASE-02c** — and as of this plan being written, **neither has shipped**: this repo's `backend/src/db/models/coaching.py` has no `ClientMessage` model yet, and the live Alembic head is `c8af0b7b55f9` (predates both PHASE-02b's `add_requested_at_to_check_ins` and PHASE-02c's `add_client_messages_table` migrations). Everything this plan says about `ChatTab` — its sub-tab switcher (`subTab` state, `TabsList`/`TabsTrigger`/`TabsContent`), its location in `frontend/src/app/(app)/clients/[clientId]/page.tsx`, its prop shape (`{ clientId: string }`) — is inferred from PHASE-02b's and PHASE-02c's **plan documents**, not from real shipped code. **Whoever executes this plan must re-read PHASE-02b's and PHASE-02c's actual shipped `ChatTab` implementation first** and adjust every frontend integration point in Tasks 10–12 below if the real component differs from what's assumed here (different state variable names, a different sub-tab library, a different prop signature, etc.). Do not assume the plan and the shipped code match. See Self-review's "Dependency risk" note.

**Goal:** A client logs a meal — mandatory photo, a description, and which of five fixed daily slots it belongs to (Breakfast / Morning Snack / Lunch / Evening Snack / Dinner) — from their own `/me/chat` page (D-31, nested as a third sub-tab alongside Text and Check-ins, mirroring D-20's grouping on the HC side). The HC sees these entries grouped by day, most recent day first, scrollable horizontally within a day, inside the Chat tab's **Logged Meals** sub-view — and can optionally react with one of three faces (happy / neutral / sad). No rated/unrated split in the display (D-26). Any real HC comment about a meal still goes through the Text view, never inline on the entry (D-4, reaffirmed by D-26).

## Design decisions flagged for SoJo's review

Per this repo's convention (see PHASE-02b Design Decision 4, PHASE-02c Design Decisions 1–3): the spec deliberately leaves some things unresolved, and this plan does not invent product answers to those. Where a working default was still needed to produce runnable code, it's called out explicitly below as provisional, not decided.

1. **The three questions D-26 explicitly pins — genuinely left unresolved here, not silently decided.** D-26's own text: "what happens when [EXIF capture-time] is missing, whether the client can correct it, and how to discourage picking an old photo instead of shooting one live... all explicitly unresolved, deliberately pinned until the actual camera/upload flow is being built." This plan *is* that camera/upload flow, so these need an answer to ship, but I'm presenting them as open choices rather than picking one:
   - **EXIF missing.** Options: (a) `captured_at` stays `NULL`, entry is still grouped/sorted by `logged_at` (server receipt time) — cheapest, no misleading data, but the "day" a meal displays under is then "day it was uploaded," not "day it was eaten," which could differ if a client logs meals in a batch later that evening or the next morning. (b) Silently fall back to `logged_at` as if it were the capture time — simpler UI (always shows *a* time) but conflates two different real facts and could mislead the HC into thinking the meal was eaten at upload time. **This plan implements (a)** as the necessary default to ship something, but this is exactly the choice D-26 flagged as pending — please confirm or override.
   - **Client correction.** Not built in this plan at all — no edit UI, no "fix the time" affordance. If SoJo wants clients to be able to correct a missing/wrong capture time, that's new scope (a PATCH endpoint + UI) not currently in any task below.
   - **Anti-gaming (discouraging an old gallery photo).** Not built. Two directions exist if SoJo wants to pursue this later: a soft client-side nudge (e.g. `<input capture="environment">` biases mobile browsers toward the live camera, but doesn't block gallery selection, has inconsistent desktop/iOS Safari support, and is trivially bypassed) vs. a soft server-side signal (flag entries where `logged_at - captured_at` exceeds some threshold, shown to the HC as a subtle "logged N days after capture" note rather than blocked) — the latter needs (a) above to hold (captured_at populated when available) before it's even possible. Neither is implemented here.

2. **`meal_logs` schema, beyond the spec's sketch.** The spec's sketch (§6) lists `id, client_id, meal_slot, description, photo_url (mandatory), captured_at NULL, hc_reaction NULL, logged_at`. Gaps filled in for this plan, each a real choice:
   - **`hc_user_id` added**, denormalized alongside `client_id` — matches this codebase's existing pattern on every other client-owned table (`CheckIn`, and PHASE-02c's `ClientMessage`), not a new convention.
   - **`photo_url` renamed to `photo_storage_path`, storing an R2 key, not a URL.** The spec's F3 §3rd-party section (written before PHASE-02b/02c existed) says "Supabase Storage... signed URLs with 1-hour expiry." That's stale: this codebase has no Supabase Storage integration at all — `backend/src/lib/s3.py` is a hand-rolled Cloudflare R2 SigV4 client — and PHASE-02c already discovered and documented (its Design Decision 3) that **no signed-URL infrastructure exists anywhere in this codebase**, building the first-ever backend-mediated download-proxy endpoint instead of inventing signed URLs. This plan follows PHASE-02c's precedent, not the spec's stale Supabase mention — flagging so SoJo can correct that stale line in `SPEC-0001-one-stop-spot.md` separately.
   - **`description` is nullable, not required**, even though the client "writes a description" per the HC-journey prose — the spec's data-model sketch marks `photo_url` explicitly `(mandatory, not nullable)` but says nothing equivalent for `description`, and the only hard requirement D-26 states is the *photo*. Treating description as optional free text is the more conservative reading (doesn't block a submission on a missing description the spec never explicitly mandated) but this is a real ambiguity — please confirm whether description should in fact be required.
   - **No uniqueness constraint on `(client_id, meal_slot, <day>)`.** The spec doesn't say whether a client can log two entries for the same slot on the same day (e.g. correcting a mislogged Breakfast by logging a second one). This plan allows unlimited entries per slot per day — simplest, reversible if SoJo wants a constraint later.
   - **`reacted_at TIMESTAMPTZ NULL` added** alongside `hc_reaction` — not in the spec's sketch, but needed to eventually support D-24's "what's new" Roster Board indicator (an unreacted meal log is one signal of what's new) — see Decision 4 below.
   - **Reaction is overwritable, entry itself is not editable.** D-25 states messages are permanent, no edit/delete — D-26 says nothing equivalent for meal log entries or HC reactions. This plan takes the position that the HC's reaction can be changed any time (low-stakes UI toggle, not a tracked commitment) but the client's own entry (photo/description/slot) has no PATCH endpoint once submitted, matching this unit's general "keep it simple, no edit flows in v1" posture elsewhere (D-25). Flagging as an assumption, not a locked decision.

3. **"Grouped by day, horizontally scrollable" — concrete component structure.** The spec's HC-journey text is: "entries grouped by day, most recent day first; within a day, entries sit side by side and scroll horizontally once there are more than a few." This plan implements it as: one vertically-stacked section per calendar day (label: e.g. "Today", "Yesterday", or the date), each section rendering an `overflow-x-auto` flex row of fixed-width meal cards, ordered within the day by `meal_slot`'s fixed sequence (Breakfast → Morning Snack → Lunch → Evening Snack → Dinner) rather than by timestamp — reasoning: the five slots are the product's own fixed ordering concept (D-26), so sorting by slot keeps "Breakfast" always visually first regardless of what time it happened to be logged, which reads more naturally to an HC scanning a day. If multiple entries share a slot (Decision 2's no-uniqueness-constraint choice), they sub-sort by `logged_at` ascending within that slot. **Which calendar day an entry belongs to also inherits Decision 1's answer** — grouped by `captured_at`'s date when present, else `logged_at`'s date, both interpreted in the client's own IST-first timezone assumption (this codebase already assumes IST throughout, e.g. PHASE-02b's Saturday-reminder cron) — flagging this as the same kind of provisional default as Decision 1, not a firm decision.

4. **D-24's Roster Board "what's new" indicator — still not built here, staying deferred.** PHASE-02c's self-review explicitly named this the natural point to build it ("PHASE-03 (Logged Meals) will be the third [signal source], and that's the natural point to build the aggregated indicator once, rather than three separate partial versions"). This plan **does not** build it — per CLAUDE.md's scope-discipline rule (§1 rule 10), the ask for this plan was specifically Logged Meals, and aggregating three signal sources (unread text, unanswered/new check-in, unreacted meal log) into one Roster Board badge is its own small cross-cutting slice of work touching the Roster Board component, not any of the three Chat sub-views. Recommending a short follow-on **PHASE-03b** for that aggregation once this phase's `reacted_at`/PHASE-02b's/PHASE-02c's signal fields all exist — flagging explicitly rather than silently dropping it, as PHASE-02c's own self-review promised.

5. **EXIF library choice and a real HEIC gap.** No EXIF-reading library exists in this repo today (confirmed: no `Pillow`/`piexif`/`exifread`/`Pillow-heif` in `backend/pyproject.toml`). Proposing **Pillow** (`Pillow>=10.0`) over `piexif` (JPEG-only, effectively unmaintained since ~2019) or `exifread` (also no HEIC support) — Pillow is actively maintained, already the de facto standard for this in Python, and its `Image.open(...).getexif()` covers JPEG/PNG/WebP/TIFF. **Real gap: none of these — including stock Pillow — decode HEIC** (the default capture format on iPhones since iOS 11) without the separate `pillow-heif` package, which binds against native `libheif` and adds real deployment complexity (a system library dependency, not just a pip package). This plan's Task 3 **does not** add `pillow-heif` — it treats HEIC uploads as "no EXIF available" (falls through to Decision 1's missing-EXIF path, so nothing breaks, `captured_at` is simply `NULL`), rather than pulling in a native-library dependency for this first slice. Flagging so SoJo can decide if native HEIC EXIF support is worth the deployment cost later, given a large fraction of client-submitted photos will likely be HEIC.

6. **EXIF may carry GPS coordinates — a real DPDP/compliance question, not implemented here.** Phone photos frequently embed a `GPSInfo` EXIF tag (the meal's physical location — plausibly the client's home). This plan extracts only `DateTimeOriginal` and discards the rest of the EXIF block — it does not strip GPS data from the *stored photo bytes themselves* (the original file, GPS tag included, is uploaded to R2 as-is; only the private download-proxy pattern from PHASE-02c gates access to it, same protection as any other client photo in this codebase). Stripping GPS from the persisted image (via Pillow re-encode) is additional processing cost and complexity this plan doesn't take on — flagging as a real, not hypothetical, privacy consideration per CLAUDE.md §9 principle 5 (PII encrypted/protected at rest) for SoJo to weigh, not something silently resolved either way.

**Architecture:** One new table (`meal_logs`), one new backend module (`backend/src/api/meal_logs.py`, HC-facing — mirrors the existing `messages.py`/`me.py` split exactly: HC routes in their own file, client routes added to `me.py`), one new S3 key-builder function (`build_meal_photo_key`, alongside `build_session_file_key`/`build_message_attachment_key` in `backend/src/lib/s3.py`), one new small EXIF-extraction module (`backend/src/lib/exif.py`), and a new download-proxy endpoint pair (HC + client variants), reusing PHASE-02c's precedent rather than inventing anything new. Frontend: `ChatTab` (introduced by PHASE-02b, extended by PHASE-02c with a Text/Check-ins switcher) gains a third sub-tab, **Logged Meals**, rendering the day-grouped horizontal-scroll view described in Decision 3; `/me/chat` (client side) gains the matching third sub-tab with a submission form plus the client's own day-grouped history.

**Tech stack:** Same as PHASE-02a/02b/02c — FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0 async, Pydantic ≥ 2.7, Alembic, Next.js/TypeScript, Vitest, Playwright. **New backend dependency: `Pillow>=10.0`** (justification: Decision 5 above) — added to `backend/pyproject.toml`'s `dependencies` list in Task 3.

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before backend commands
- **Verified-against note (final review, PHASE-03):** the shared `hc_pf` venv above is used across multiple worktrees and, as of this phase's final review, doesn't have `Pillow`/`piexif` installed — it can't even import `src.main`. This phase's code was actually verified against `backend/.venv` (this worktree's own uv-managed venv: `cd backend && uv sync && source .venv/bin/activate`), which is also what production's Docker build uses. `hc_pf` was intentionally left untouched rather than installed into, since it's shared infrastructure outside this phase's blast radius.
- Backend tests hit a real PostgreSQL DB (`tapas_test`) — no DB mocking; mock `s3_put`/`s3_get` exactly as `test_file_upload.py` and PHASE-02c's `test_messages.py` already do (`patch("src.api.meal_logs.s3_put", new_callable=AsyncMock)` / `patch("src.api.me.s3_put", new_callable=AsyncMock)`, matching whichever module the route lives in)
- After the migration lands, run `alembic upgrade head` against `tapas_dev` too (`DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/tapas_dev alembic upgrade head`), not just `tapas_test`
- **Migration chaining risk (real, see the dependency callout at the top of this file):** as of this plan being written, the true Alembic head is `c8af0b7b55f9` (`add_google_calendar_event_title_to_sessions`) — neither PHASE-02b's nor PHASE-02c's migrations have landed. Task 1's `down_revision` is written against `c8af0b7b55f9` below, but **whoever executes this plan must run `alembic heads` first** and rebase `down_revision` onto whatever the real head is by then (almost certainly PHASE-02c's `add_client_messages_table` revision, if it ships first as its dependency ordering implies)
- Every API module in this codebase defines its own private `_get_owned_client` helper rather than importing a shared one (confirmed convention in `clients.py`, `supplements.py`, `diet_charts.py`, PHASE-02c's `messages.py`) — `meal_logs.py` follows the same convention
- No signed-URL infrastructure exists or should be invented — reuse the download-proxy pattern exactly (Decision 2 above)
- Follow this app's existing Tailwind/design-token conventions exactly (see PHASE-02a's Global Constraints for the specific classes already in use)

---

## Task 1: `meal_logs` table + model

**Files:**
- Create: `backend/alembic/versions/<new_revision>_add_meal_logs_table.py`
- Modify: `backend/src/db/models/coaching.py` (add `MealLog`)
- Modify: `backend/src/db/models/__init__.py` (export `MealLog`)

**Interfaces:**
- Produces: `MealLog(id, client_id, hc_user_id, meal_slot, description, photo_storage_path, photo_original_filename, photo_mime_type, captured_at, logged_at, hc_reaction, reacted_at)` — every task below consumes this model.

- [ ] **Step 1.1: Check current migration head**

Run: `cd backend && alembic heads`. **Do not assume it's `c8af0b7b55f9`** — per the Global Constraints note above, re-verify against whatever PHASE-02b/02c have actually landed by execution time, and set `down_revision` accordingly.

- [ ] **Step 1.2: Generate and write the migration**

Run: `cd backend && alembic revision -m "add_meal_logs_table"`

```python
"""add_meal_logs_table

Revision ID: <generated>
Revises: <real current head — verify per Step 1.1>
Create Date: <generated>
"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "<real current head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hc_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("meal_slot", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("photo_storage_path", sa.Text, nullable=False),
        sa.Column("photo_original_filename", sa.Text, nullable=False),
        sa.Column("photo_mime_type", sa.Text, nullable=False),
        sa.Column("captured_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("logged_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("hc_reaction", sa.Text, nullable=True),
        sa.Column("reacted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "meal_slot IN ('breakfast', 'morning_snack', 'lunch', 'evening_snack', 'dinner')",
            name="ck_meal_logs_meal_slot",
        ),
        sa.CheckConstraint(
            "hc_reaction IN ('happy', 'neutral', 'sad') OR hc_reaction IS NULL",
            name="ck_meal_logs_hc_reaction",
        ),
    )
    op.create_index("idx_meal_logs_client_logged", "meal_logs", ["client_id", "logged_at"])


def downgrade() -> None:
    op.drop_index("idx_meal_logs_client_logged", table_name="meal_logs")
    op.drop_table("meal_logs")
```

- [ ] **Step 1.3: Add the model**

In `backend/src/db/models/coaching.py`, update the module docstring to include `meal_logs` and add:

```python
class MealLog(Base):
    __tablename__ = "meal_logs"
    __table_args__ = (Index("idx_meal_logs_client_logged", "client_id", "logged_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    meal_slot: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    photo_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    photo_original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    photo_mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    logged_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    hc_reaction: Mapped[str | None] = mapped_column(Text)
    reacted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
```

Add `MealLog` to `backend/src/db/models/__init__.py`'s import from `coaching` and to `__all__`, matching how `ClientMessage` was added there in PHASE-02c Task 1.

- [ ] **Step 1.4: Run — apply and verify**

```bash
cd backend && alembic upgrade head
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/tapas_dev alembic upgrade head
```

- [ ] **Step 1.5: Commit**

```bash
git add backend/alembic/versions/ backend/src/db/models/coaching.py backend/src/db/models/__init__.py
git commit -m "feat(meal-logs): meal_logs table + model (PHASE-03 Task 1)"
```

---

## Task 2: S3 key-builder for meal photos

**Files:**
- Modify: `backend/src/lib/s3.py`
- Test: `backend/tests/unit/test_s3.py` (extend)

**Interfaces:**
- Produces: `build_meal_photo_key(client_id: UUID, meal_log_id: UUID, filename: str) -> str` — Task 4 consumes this.

- [ ] **Step 2.1: Write the failing test**

```python
def test_build_meal_photo_key_structure():
    from src.lib.s3 import build_meal_photo_key
    import uuid
    client_id, meal_log_id = uuid.uuid4(), uuid.uuid4()
    key = build_meal_photo_key(client_id, meal_log_id, "breakfast.jpg")
    assert key == f"client-{client_id}/meal-logs/{meal_log_id}/breakfast.jpg"


def test_build_meal_photo_key_sanitizes_filename():
    from src.lib.s3 import build_meal_photo_key
    import uuid
    key = build_meal_photo_key(uuid.uuid4(), uuid.uuid4(), "my meal (1)!.heic")
    assert " " not in key and "(" not in key and "!" not in key
```

- [ ] **Step 2.2: Run — confirm failure**

Run: `cd backend && pytest tests/unit/test_s3.py -k meal_photo -v`

- [ ] **Step 2.3: Implement**

Add to `backend/src/lib/s3.py`, right below `build_message_attachment_key` (if PHASE-02c has landed by then) or below `build_session_file_key` otherwise:

```python
def build_meal_photo_key(client_id: UUID, meal_log_id: UUID, filename: str) -> str:
    """Returns R2 key: client-{client_id}/meal-logs/{meal_log_id}/{sanitized_filename}"""
    sanitized_file = _sanitize(filename, max_len=200)
    return f"client-{client_id}/meal-logs/{meal_log_id}/{sanitized_file}"
```

- [ ] **Step 2.4: Run — confirm pass, then commit**

```bash
cd backend && pytest tests/unit/test_s3.py -v
git add backend/src/lib/s3.py backend/tests/unit/test_s3.py
git commit -m "feat(meal-logs): S3 key-builder for meal photos (PHASE-03 Task 2)"
```

---

## Task 3: EXIF capture-time extraction helper + Pillow dependency

**Files:**
- Modify: `backend/pyproject.toml` (add `Pillow>=10.0` to `dependencies`)
- Create: `backend/src/lib/exif.py`
- Test: `backend/tests/unit/test_exif.py` (new)

**Interfaces:**
- Produces: `extract_capture_time(image_bytes: bytes, mime_type: str) -> datetime | None` — Task 4 consumes this. Returns `None` (never raises) whenever EXIF is absent, unparseable, or the format isn't supported (per Decision 5, this includes all HEIC images in this plan) — Decision 1's missing-EXIF path always has a value to fall back to.

- [ ] **Step 3.1: Add the dependency**

In `backend/pyproject.toml`, add `"Pillow>=10.0",` to the `dependencies` list (alongside `resend>=2.0`, etc.). Run `cd backend && uv sync` (or this repo's equivalent lockfile-sync command — check `backend/README.md` or existing CI config for the exact command if `uv` isn't confirmed) to install it before writing tests that import `PIL`.

- [ ] **Step 3.2: Write the failing tests**

```python
# backend/tests/unit/test_exif.py
import io
from datetime import datetime

from PIL import Image
import piexif  # dev-only, test-fixture generation — NOT added as a runtime dependency, see note below
import pytest

from src.lib.exif import extract_capture_time


def _jpeg_with_datetime_original(dt_str: str) -> bytes:
    """Build a minimal in-memory JPEG with a DateTimeOriginal EXIF tag for testing.
    Uses piexif only to construct the test fixture bytes — not a plan dependency."""
    img = Image.new("RGB", (4, 4))
    exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: dt_str.encode()}}
    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="jpeg", exif=exif_bytes)
    return buf.getvalue()


def test_extracts_datetime_original_from_jpeg():
    photo = _jpeg_with_datetime_original("2026:07:15 08:30:00")
    result = extract_capture_time(photo, "image/jpeg")
    assert result == datetime(2026, 7, 15, 8, 30, 0)


def test_returns_none_for_jpeg_with_no_exif():
    img = Image.new("RGB", (4, 4))
    buf = io.BytesIO()
    img.save(buf, format="jpeg")
    assert extract_capture_time(buf.getvalue(), "image/jpeg") is None


def test_returns_none_for_heic_without_raising():
    # Stock Pillow cannot decode HEIC at all (Decision 5) — must degrade gracefully, never 500.
    fake_heic_bytes = b"not a real heic file, just bytes with the right content-type"
    assert extract_capture_time(fake_heic_bytes, "image/heic") is None


def test_returns_none_for_corrupt_bytes_without_raising():
    assert extract_capture_time(b"\x00\x01garbage", "image/jpeg") is None
```

Add `piexif` as a **dev-only** test dependency (`backend/pyproject.toml`'s `[dependency-groups] dev` list) — it's used solely to *construct* EXIF-bearing JPEG fixtures for this test file, never imported by application code.

- [ ] **Step 3.3: Run — confirm failure**

Run: `cd backend && pytest tests/unit/test_exif.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3.4: Implement**

```python
# backend/src/lib/exif.py
"""EXIF capture-time extraction for meal photos (D-26). Deliberately conservative:
any failure to parse (unsupported format, corrupt bytes, missing tag) returns None
rather than raising — a meal log must never fail to save because of unreadable EXIF.
See PHASE-03 Design Decisions 1 and 5 for why missing/HEIC both resolve to None here,
not an error and not a synthesized fallback timestamp."""
from __future__ import annotations

import io
from datetime import datetime

from PIL import ExifTags, Image

_DATETIME_ORIGINAL_TAG = next(
    tag_id for tag_id, name in ExifTags.TAGS.items() if name == "DateTimeOriginal"
)

# EXIF's own datetime string format, e.g. "2026:07:15 08:30:00" — colons in the date
# portion, not hyphens, per the EXIF 2.3 spec.
_EXIF_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def extract_capture_time(image_bytes: bytes, mime_type: str) -> datetime | None:
    """Best-effort extraction of DateTimeOriginal. Returns None for any of:
    unsupported format (incl. all HEIC — stock Pillow can't decode it, Decision 5),
    no EXIF block, no DateTimeOriginal tag, or an unparseable value. Never raises."""
    if mime_type == "image/heic":
        return None

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            exif = img.getexif()
            raw_value = exif.get(_DATETIME_ORIGINAL_TAG)
            if not raw_value:
                return None
            return datetime.strptime(raw_value, _EXIF_DATETIME_FORMAT)
    except Exception:
        return None
```

- [ ] **Step 3.5: Run — confirm pass, then commit**

```bash
cd backend && pytest tests/unit/test_exif.py -v
git add backend/pyproject.toml backend/src/lib/exif.py backend/tests/unit/test_exif.py
git commit -m "feat(meal-logs): EXIF capture-time extraction helper, Pillow dependency (PHASE-03 Task 3)"
```

---

## Task 4: Client-facing submit endpoint — `POST /api/me/meal-logs`

**Files:**
- Modify: `backend/src/api/me.py`
- Test: `backend/tests/integration/test_me.py` (extend)

**Interfaces:**
- Consumes: `build_meal_photo_key` (Task 2), `extract_capture_time` (Task 3), `s3_put` (existing).
- Produces: `MealLogOut{id, client_id, hc_user_id, meal_slot, description, photo_original_filename, photo_mime_type, captured_at, logged_at, hc_reaction, reacted_at}`, defined in `meal_logs.py` (Task 5) and imported into `me.py` — same cross-import pattern as `CheckInOut`/`MessageOut`.

- [ ] **Step 4.1: Write the failing tests**

```python
ALLOWED_MEAL_PHOTO_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}  # see meal_logs.py, Task 5


@pytest.mark.asyncio
async def test_client_can_log_meal_with_photo(http_client, client_headers, client_rec):
    from unittest.mock import AsyncMock, patch
    with patch("src.api.me.s3_put", new_callable=AsyncMock) as mock_put, \
         patch("src.api.me.extract_capture_time", return_value=None):
        r = await http_client.post(
            "/api/me/meal-logs", headers=client_headers,
            data={"meal_slot": "breakfast", "description": "Idli and sambar"},
            files={"photo": ("breakfast.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["meal_slot"] == "breakfast"
    assert body["description"] == "Idli and sambar"
    assert body["captured_at"] is None
    assert body["hc_reaction"] is None
    mock_put.assert_awaited_once()


@pytest.mark.asyncio
async def test_meal_log_rejects_missing_photo(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/meal-logs", headers=client_headers,
        data={"meal_slot": "lunch", "description": "Dal and rice"},
    )
    assert r.status_code == 422  # photo is a required field, D-26


@pytest.mark.asyncio
async def test_meal_log_rejects_invalid_meal_slot(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/meal-logs", headers=client_headers,
        data={"meal_slot": "brunch"},  # not one of the five fixed slots
        files={"photo": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_meal_log_rejects_non_image_photo(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/meal-logs", headers=client_headers,
        data={"meal_slot": "dinner"},
        files={"photo": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_meal_log_uses_extracted_capture_time_when_present(http_client, client_headers, client_rec):
    from datetime import datetime
    from unittest.mock import AsyncMock, patch
    with patch("src.api.me.s3_put", new_callable=AsyncMock), \
         patch("src.api.me.extract_capture_time", return_value=datetime(2026, 7, 20, 7, 45, 0)):
        r = await http_client.post(
            "/api/me/meal-logs", headers=client_headers,
            data={"meal_slot": "breakfast"},
            files={"photo": ("b.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201
    assert r.json()["captured_at"] is not None
```

- [ ] **Step 4.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_me.py -k meal_log -v`

- [ ] **Step 4.3: Implement**

Add to the imports at the top of `backend/src/api/me.py`:

```python
from src.api.meal_logs import ALLOWED_MEAL_PHOTO_MIME_TYPES, MAX_MEAL_PHOTO_SIZE_BYTES, MealLogOut
from src.db.models import MealLog
from src.lib.exif import extract_capture_time
from src.lib.s3 import build_meal_photo_key, s3_get, s3_put
```

Add the route:

```python
@router.post("/meal-logs", status_code=status.HTTP_201_CREATED)
async def submit_my_meal_log(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    meal_slot: str = Form(...),
    description: str | None = Form(None),
    photo: UploadFile = File(...),  # required — D-26, no optional-photo path
) -> MealLogOut:
    client = await _resolve_client(db, claims, hc_id)

    valid_slots = {"breakfast", "morning_snack", "lunch", "evening_snack", "dinner"}
    if meal_slot not in valid_slots:
        raise HTTPException(status_code=422, detail=f"meal_slot must be one of {sorted(valid_slots)}")

    if not photo.content_type or photo.content_type not in ALLOWED_MEAL_PHOTO_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported photo type. Allowed: {sorted(ALLOWED_MEAL_PHOTO_MIME_TYPES)}",
        )
    content = await photo.read()
    if len(content) > MAX_MEAL_PHOTO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Photo exceeds the 10 MB limit")

    captured_at = extract_capture_time(content, photo.content_type)  # None per Decision 1 if absent/HEIC/corrupt

    meal_log = MealLog(
        client_id=client.id,
        hc_user_id=UUID(hc_id),
        meal_slot=meal_slot,
        description=description,
        captured_at=captured_at,
    )
    db.add(meal_log)
    await db.flush()  # need meal_log.id for the storage key

    key = build_meal_photo_key(client.id, meal_log.id, photo.filename or "unnamed")
    await s3_put(key, content, photo.content_type)
    meal_log.photo_storage_path = key
    meal_log.photo_original_filename = photo.filename or "unnamed"
    meal_log.photo_mime_type = photo.content_type

    await db.commit()
    await db.refresh(meal_log)
    return MealLogOut.model_validate(meal_log)
```

(`File` needs importing from `fastapi` alongside the existing `Form`/`UploadFile` imports in `me.py` if not already present.)

- [ ] **Step 4.4: Run — confirm pass, then full backend suite**

```bash
cd backend && pytest tests/integration/test_me.py -v && pytest -x
```

- [ ] **Step 4.5: Commit**

```bash
git add backend/src/api/me.py backend/tests/integration/test_me.py
git commit -m "feat(me): client submits a meal log with mandatory photo + EXIF capture-time (PHASE-03 Task 4, D-26)"
```

---

## Task 5: `MealLogOut` schema + HC-facing list/react endpoints — `backend/src/api/meal_logs.py`

**Files:**
- Create: `backend/src/api/meal_logs.py`
- Modify: `backend/src/main.py` (register `meal_logs_router`)
- Test: `backend/tests/integration/test_meal_logs.py` (new)

**Interfaces:**
- Produces: `MealLogOut` (consumed by `me.py`, Task 4), `GET /api/clients/{client_id}/meal-logs -> PaginatedList[MealLogOut]`, `POST /api/clients/{client_id}/meal-logs/{meal_log_id}/react -> MealLogOut` — Task 10 (frontend HC wrappers) consumes both.

- [ ] **Step 5.1: Write the failing tests**

```python
# backend/tests/integration/test_meal_logs.py
from unittest.mock import AsyncMock, patch

import pytest


async def _make_client(http_client, headers) -> dict:
    import uuid
    r = await http_client.post("/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 201
    return r.json()


async def _log_meal(http_client, client_headers, meal_slot="breakfast"):
    with patch("src.api.me.s3_put", new_callable=AsyncMock), \
         patch("src.api.me.extract_capture_time", return_value=None):
        r = await http_client.post(
            "/api/me/meal-logs", headers=client_headers,
            data={"meal_slot": meal_slot, "description": "test meal"},
            files={"photo": ("m.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_hc_lists_client_meal_logs(http_client, hc_headers, client_headers, client_rec):
    await _log_meal(http_client, client_headers)
    r = await http_client.get(f"/api/clients/{client_rec.id}/meal-logs", headers=hc_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_meal_logs_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/meal-logs", headers=hc2_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_hc_can_react_to_a_meal_log(http_client, hc_headers, client_headers, client_rec):
    meal = await _log_meal(http_client, client_headers)
    r = await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal['id']}/react",
        headers=hc_headers, json={"reaction": "happy"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["hc_reaction"] == "happy"
    assert r.json()["reacted_at"] is not None


@pytest.mark.asyncio
async def test_hc_can_change_reaction(http_client, hc_headers, client_headers, client_rec):
    meal = await _log_meal(http_client, client_headers)
    await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal['id']}/react",
        headers=hc_headers, json={"reaction": "sad"},
    )
    r2 = await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal['id']}/react",
        headers=hc_headers, json={"reaction": "happy"},
    )
    assert r2.json()["hc_reaction"] == "happy"  # overwritable — Design Decision 2


@pytest.mark.asyncio
async def test_react_rejects_invalid_value(http_client, hc_headers, client_headers, client_rec):
    meal = await _log_meal(http_client, client_headers)
    r = await http_client.post(
        f"/api/clients/{client_rec.id}/meal-logs/{meal['id']}/react",
        headers=hc_headers, json={"reaction": "angry"},
    )
    assert r.status_code == 422
```

- [ ] **Step 5.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_meal_logs.py -v`
Expected: FAIL — module/routes don't exist

- [ ] **Step 5.3: Implement**

```python
# backend/src/api/meal_logs.py
"""HC-side meal_logs list/react endpoints. Client-side submit lives in me.py."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.db.models import Client, MealLog

router = APIRouter(tags=["meal-logs"])

ALLOWED_MEAL_PHOTO_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_MEAL_PHOTO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB — matches PHASE-02c's message-attachment cap
VALID_REACTIONS = {"happy", "neutral", "sad"}


# ── schemas ────────────────────────────────────────────────────────────────────


class MealLogOut(BaseModel):
    id: UUID
    client_id: UUID
    hc_user_id: UUID
    meal_slot: str
    description: str | None
    photo_original_filename: str
    photo_mime_type: str
    captured_at: datetime | None
    logged_at: datetime
    hc_reaction: str | None
    reacted_at: datetime | None

    model_config = {"from_attributes": True}


class MealLogReactIn(BaseModel):
    reaction: str


# ── shared helper (this module's own copy — see Global Constraints) ────────────


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/api/clients/{client_id}/meal-logs")
async def list_client_meal_logs(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 40,  # higher default than messages/check-ins — day-grouping wants more per page
    cursor: str | None = None,
) -> PaginatedList[MealLogOut]:
    await _get_owned_client(db, client_id, hc_id)

    q = select(MealLog).where(MealLog.client_id == client_id)
    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                MealLog.logged_at < cur_ts,
                and_(MealLog.logged_at == cur_ts, MealLog.id < cur_id),
            )
        )
    q = q.order_by(MealLog.logged_at.desc(), MealLog.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].logged_at, rows[-1].id)

    return PaginatedList(items=[MealLogOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.post("/api/clients/{client_id}/meal-logs/{meal_log_id}/react")
async def react_to_meal_log(
    client_id: UUID,
    meal_log_id: UUID,
    body: MealLogReactIn,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MealLogOut:
    await _get_owned_client(db, client_id, hc_id)

    if body.reaction not in VALID_REACTIONS:
        raise HTTPException(status_code=422, detail=f"reaction must be one of {sorted(VALID_REACTIONS)}")

    meal_log = (await db.execute(
        select(MealLog).where(MealLog.id == meal_log_id, MealLog.client_id == client_id)
    )).scalar_one_or_none()
    if meal_log is None:
        raise HTTPException(status_code=404, detail="Meal log not found")

    meal_log.hc_reaction = body.reaction
    meal_log.reacted_at = datetime.now(tz=meal_log.logged_at.tzinfo)

    await db.commit()
    await db.refresh(meal_log)
    return MealLogOut.model_validate(meal_log)
```

Register the router in `backend/src/main.py`, mirroring how `check_ins_router`/`messages_router` are included:

```python
from src.api.meal_logs import router as meal_logs_router
# ...
app.include_router(meal_logs_router)
```

- [ ] **Step 5.4: Run — confirm pass, then full backend suite**

```bash
cd backend && pytest tests/integration/test_meal_logs.py -v && pytest -x
```

- [ ] **Step 5.5: Commit**

```bash
git add backend/src/api/meal_logs.py backend/src/main.py backend/tests/integration/test_meal_logs.py
git commit -m "feat(meal-logs): HC-side list + 3-option react endpoints (PHASE-03 Task 5, D-26)"
```

---

## Task 6: Client-facing list endpoint — `GET /api/me/meal-logs`

**Files:**
- Modify: `backend/src/api/me.py`
- Test: `backend/tests/integration/test_me.py` (extend)

**Interfaces:**
- Consumes: `MealLogOut` (Task 5).
- Produces: `GET /api/me/meal-logs -> PaginatedList[MealLogOut]` — Task 12 (client-facing frontend view) consumes this.

- [ ] **Step 6.1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_client_lists_own_meal_logs(http_client, client_headers, client_rec):
    from unittest.mock import AsyncMock, patch
    with patch("src.api.me.s3_put", new_callable=AsyncMock), \
         patch("src.api.me.extract_capture_time", return_value=None):
        await http_client.post(
            "/api/me/meal-logs", headers=client_headers,
            data={"meal_slot": "lunch"},
            files={"photo": ("l.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    r = await http_client.get("/api/me/meal-logs", headers=client_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


@pytest.mark.asyncio
async def test_client_cannot_see_other_clients_meal_logs(http_client, hc_headers, client_headers, db):
    from unittest.mock import AsyncMock, patch
    other = (await http_client.post("/api/clients", headers=hc_headers, json={"full_name": "Other"})).json()
    # HC cannot log a meal on the client's behalf — no such endpoint exists (client-only action).
    # This test just confirms the list is scoped to the caller's own client row via ClientClaimsDep.
    r = await http_client.get("/api/me/meal-logs", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []
```

- [ ] **Step 6.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_me.py -k "meal_log and list" -v`

- [ ] **Step 6.3: Implement**

Add to `backend/src/api/me.py`:

```python
@router.get("/meal-logs")
async def list_my_meal_logs(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 40,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[MealLogOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(MealLog).where(MealLog.client_id == client.id)
    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                MealLog.logged_at < cur_ts,
                and_(MealLog.logged_at == cur_ts, MealLog.id < cur_id),
            )
        )
    q = q.order_by(MealLog.logged_at.desc(), MealLog.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].logged_at, rows[-1].id)

    return PaginatedList(items=[MealLogOut.model_validate(r) for r in rows], next_cursor=next_cursor)
```

- [ ] **Step 6.4: Run — confirm pass, then commit**

```bash
cd backend && pytest tests/integration/test_me.py -v
git add backend/src/api/me.py backend/tests/integration/test_me.py
git commit -m "feat(me): client lists own meal logs (PHASE-03 Task 6)"
```

---

## Task 7: HC-facing photo download-proxy — `GET /api/clients/{client_id}/meal-logs/{id}/photo`

**Files:**
- Modify: `backend/src/api/meal_logs.py`
- Test: `backend/tests/integration/test_meal_logs.py` (extend)

**Interfaces:**
- Consumes: `s3_get` (existing).
- Produces: raw photo bytes with `Content-Disposition: inline` — Task 11 (HC frontend) renders these as `<img src="...">`.

- [ ] **Step 7.1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_hc_can_download_meal_photo(http_client, hc_headers, client_headers, client_rec):
    from unittest.mock import AsyncMock, patch
    meal = await _log_meal(http_client, client_headers)
    with patch("src.api.meal_logs.s3_get", new_callable=AsyncMock, return_value=b"\xff\xd8\xff-fake-jpeg"):
        r = await http_client.get(
            f"/api/clients/{client_rec.id}/meal-logs/{meal['id']}/photo", headers=hc_headers,
        )
    assert r.status_code == 200
    assert r.content == b"\xff\xd8\xff-fake-jpeg"
    assert r.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_photo_download_cross_tenant_returns_404(http_client, hc_headers, hc2_headers, client_headers, client_rec):
    meal = await _log_meal(http_client, client_headers)
    r = await http_client.get(
        f"/api/clients/{client_rec.id}/meal-logs/{meal['id']}/photo", headers=hc2_headers,
    )
    assert r.status_code == 404
```

- [ ] **Step 7.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_meal_logs.py -k photo -v`

- [ ] **Step 7.3: Implement**

Add to `backend/src/api/meal_logs.py` (needs `Response` from `fastapi` and `s3_get` imported):

```python
from fastapi import Response
from src.lib.s3 import s3_get


@router.get("/api/clients/{client_id}/meal-logs/{meal_log_id}/photo")
async def get_meal_log_photo(
    client_id: UUID,
    meal_log_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> Response:
    await _get_owned_client(db, client_id, hc_id)
    meal_log = (await db.execute(
        select(MealLog).where(MealLog.id == meal_log_id, MealLog.client_id == client_id)
    )).scalar_one_or_none()
    if meal_log is None:
        raise HTTPException(status_code=404, detail="Meal log not found")

    content = await s3_get(meal_log.photo_storage_path)
    return Response(
        content=content,
        media_type=meal_log.photo_mime_type,
        headers={"Content-Disposition": f'inline; filename="{meal_log.photo_original_filename}"'},
    )
```

- [ ] **Step 7.4: Run — confirm pass, then commit**

```bash
cd backend && pytest tests/integration/test_meal_logs.py -v
git add backend/src/api/meal_logs.py backend/tests/integration/test_meal_logs.py
git commit -m "feat(meal-logs): HC-side photo download-proxy (PHASE-03 Task 7)"
```

---

## Task 8: Client-facing photo download-proxy — `GET /api/me/meal-logs/{id}/photo`

**Files:**
- Modify: `backend/src/api/me.py`
- Test: `backend/tests/integration/test_me.py` (extend)

**Interfaces:**
- Produces: the client's own version of Task 7, scoped to their own `client_id` via `ClientClaimsDep` — Task 12 (client frontend) renders these.

- [ ] **Step 8.1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_client_can_download_own_meal_photo(http_client, client_headers, client_rec):
    from unittest.mock import AsyncMock, patch
    meal = await _log_meal(http_client, client_headers)
    with patch("src.api.me.s3_get", new_callable=AsyncMock, return_value=b"\xff\xd8\xff-fake"):
        r = await http_client.get(f"/api/me/meal-logs/{meal['id']}/photo", headers=client_headers)
    assert r.status_code == 200
    assert r.content == b"\xff\xd8\xff-fake"
```

- [ ] **Step 8.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_me.py -k meal_photo -v`

- [ ] **Step 8.3: Implement**

Add to `backend/src/api/me.py`:

```python
@router.get("/meal-logs/{meal_log_id}/photo")
async def get_my_meal_log_photo(
    meal_log_id: UUID,
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> Response:
    client = await _resolve_client(db, claims, hc_id)
    meal_log = (await db.execute(
        select(MealLog).where(MealLog.id == meal_log_id, MealLog.client_id == client.id)
    )).scalar_one_or_none()
    if meal_log is None:
        raise HTTPException(status_code=404, detail="Meal log not found")

    content = await s3_get(meal_log.photo_storage_path)
    return Response(
        content=content,
        media_type=meal_log.photo_mime_type,
        headers={"Content-Disposition": f'inline; filename="{meal_log.photo_original_filename}"'},
    )
```

- [ ] **Step 8.4: Run — confirm pass, then full backend suite, then commit**

```bash
cd backend && pytest tests/integration/test_me.py -v && pytest -x
git add backend/src/api/me.py backend/tests/integration/test_me.py
git commit -m "feat(me): client-side photo download-proxy (PHASE-03 Task 8)"
```

---

## Task 9: Frontend — `mealLogs.ts` API wrappers (shared HC + client)

**Files:**
- Create: `frontend/src/lib/api/mealLogs.ts`

**Interfaces:**
- Produces: `MealLogOutSchema`/`MealLogOut` type, `listClientMealLogs(clientId)`, `reactToMealLog(clientId, mealLogId, reaction)`, `mealLogPhotoUrl(clientId, mealLogId)` (HC-side); `listMyMealLogs()`, `submitMyMealLog(input)`, `myMealLogPhotoUrl(mealLogId)` (client-side) — Tasks 11/12 consume these.

- [ ] **Step 9.1: Implement**

```ts
// frontend/src/lib/api/mealLogs.ts
import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

export const MEAL_SLOTS = ["breakfast", "morning_snack", "lunch", "evening_snack", "dinner"] as const;
export type MealSlot = (typeof MEAL_SLOTS)[number];

export const MEAL_SLOT_LABELS: Record<MealSlot, string> = {
  breakfast: "Breakfast",
  morning_snack: "Morning Snack",
  lunch: "Lunch",
  evening_snack: "Evening Snack",
  dinner: "Dinner",
};

export const MealLogOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  hc_user_id: z.string(),
  meal_slot: z.enum(MEAL_SLOTS),
  description: z.string().nullable(),
  photo_original_filename: z.string(),
  photo_mime_type: z.string(),
  captured_at: z.string().nullable(),
  logged_at: z.string(),
  hc_reaction: z.enum(["happy", "neutral", "sad"]).nullable(),
  reacted_at: z.string().nullable(),
});
export type MealLogOut = z.infer<typeof MealLogOutSchema>;

const PaginatedMealLogsSchema = z.object({
  items: z.array(MealLogOutSchema),
  next_cursor: z.string().nullable(),
});

// ── HC-side ──────────────────────────────────────────────────────────────────

export async function listClientMealLogs(clientId: string): Promise<{ items: MealLogOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/meal-logs`);
  if (!res.ok) throw new Error(`List meal logs failed: ${res.status}`);
  return PaginatedMealLogsSchema.parse(await res.json());
}

export async function reactToMealLog(
  clientId: string, mealLogId: string, reaction: "happy" | "neutral" | "sad",
): Promise<MealLogOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/meal-logs/${mealLogId}/react`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reaction }),
  });
  if (!res.ok) throw new Error(`React to meal log failed: ${res.status}`);
  return MealLogOutSchema.parse(await res.json());
}

export function mealLogPhotoUrl(clientId: string, mealLogId: string): string {
  return `${API_URL}/api/clients/${clientId}/meal-logs/${mealLogId}/photo`;
}

// ── client-side ──────────────────────────────────────────────────────────────

export async function listMyMealLogs(): Promise<{ items: MealLogOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/meal-logs`);
  if (!res.ok) throw new Error(`List my meal logs failed: ${res.status}`);
  return PaginatedMealLogsSchema.parse(await res.json());
}

export async function submitMyMealLog(input: { mealSlot: MealSlot; description?: string; photo: File }): Promise<MealLogOut> {
  const form = new FormData();
  form.append("meal_slot", input.mealSlot);
  if (input.description) form.append("description", input.description);
  form.append("photo", input.photo);

  const res = await fetchWithAuth(`${API_URL}/api/me/meal-logs`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Submit meal log failed: ${res.status}`);
  return MealLogOutSchema.parse(await res.json());
}

export function myMealLogPhotoUrl(mealLogId: string): string {
  return `${API_URL}/api/me/meal-logs/${mealLogId}/photo`;
}
```

- [ ] **Step 9.2: Unit test the schema/wrappers**

Add `frontend/tests/unit/mealLogs-api.test.ts`, one `it(...)` per exported function, mocking `fetchWithAuth` — same style as `frontend/tests/unit/me-api.test.ts`'s existing tests.

- [ ] **Step 9.3: Run — confirm pass, then commit**

```bash
cd frontend && npx vitest run tests/unit/mealLogs-api.test.ts
git add frontend/src/lib/api/mealLogs.ts frontend/tests/unit/mealLogs-api.test.ts
git commit -m "feat(meal-logs): frontend API wrappers, HC + client side (PHASE-03 Task 9)"
```

---

## Task 10: Frontend — `MealCard` + day-grouping helper (shared building block)

**Files:**
- Create: `frontend/src/components/meal-logs/MealCard.tsx`
- Create: `frontend/src/components/meal-logs/groupByDay.ts`
- Test: `frontend/tests/unit/groupByDay.test.ts` (new)

**Interfaces:**
- Produces: `groupMealLogsByDay(logs: MealLogOut[]): { day: string; entries: MealLogOut[] }[]` (Decision 3: groups by `captured_at`'s date if present, else `logged_at`'s date; within a day, sub-sorts by the fixed slot order, then `logged_at` ascending within a shared slot) — consumed by both Task 11 (HC view) and Task 12 (client view), so the grouping logic is written once, not duplicated.
- `MealCard` — one meal's photo/description/slot label/reaction, used read-only in both HC and client views (the HC view additionally overlays the reaction picker, added in Task 11, on top of this shared card).

- [ ] **Step 10.1: Write the failing test**

```ts
// frontend/tests/unit/groupByDay.test.ts
import { describe, expect, it } from "vitest";
import { groupMealLogsByDay } from "@/components/meal-logs/groupByDay";
import type { MealLogOut } from "@/lib/api/mealLogs";

function meal(overrides: Partial<MealLogOut>): MealLogOut {
  return {
    id: "1", client_id: "c1", hc_user_id: "hc1",
    meal_slot: "breakfast", description: null,
    photo_original_filename: "x.jpg", photo_mime_type: "image/jpeg",
    captured_at: null, logged_at: "2026-07-20T08:00:00Z",
    hc_reaction: null, reacted_at: null,
    ...overrides,
  };
}

describe("groupMealLogsByDay", () => {
  it("groups by captured_at's date when present", () => {
    const logs = [meal({ id: "a", captured_at: "2026-07-19T23:00:00Z", logged_at: "2026-07-20T06:00:00Z" })];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].day).toBe("2026-07-19");
  });

  it("falls back to logged_at's date when captured_at is null", () => {
    const logs = [meal({ id: "a", captured_at: null, logged_at: "2026-07-20T06:00:00Z" })];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].day).toBe("2026-07-20");
  });

  it("orders entries within a day by fixed meal-slot sequence, not by time", () => {
    const logs = [
      meal({ id: "dinner", meal_slot: "dinner", logged_at: "2026-07-20T20:00:00Z" }),
      meal({ id: "breakfast", meal_slot: "breakfast", logged_at: "2026-07-20T08:00:00Z" }),
    ];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].entries.map((e) => e.id)).toEqual(["breakfast", "dinner"]);
  });

  it("orders days most-recent-first", () => {
    const logs = [
      meal({ id: "old", logged_at: "2026-07-18T08:00:00Z" }),
      meal({ id: "new", logged_at: "2026-07-20T08:00:00Z" }),
    ];
    const groups = groupMealLogsByDay(logs);
    expect(groups.map((g) => g.day)).toEqual(["2026-07-20", "2026-07-18"]);
  });
});
```

- [ ] **Step 10.2: Run — confirm failure**

Run: `cd frontend && npx vitest run tests/unit/groupByDay.test.ts`

- [ ] **Step 10.3: Implement**

```ts
// frontend/src/components/meal-logs/groupByDay.ts
import { MEAL_SLOTS, type MealLogOut, type MealSlot } from "@/lib/api/mealLogs";

const SLOT_ORDER: Record<MealSlot, number> = Object.fromEntries(
  MEAL_SLOTS.map((slot, i) => [slot, i]),
) as Record<MealSlot, number>;

function dayKey(log: MealLogOut): string {
  // Decision 3/1: captured_at's date when present, else logged_at's — both read in local time,
  // matching this app's IST-first assumption elsewhere (e.g. PHASE-02b's Saturday cron).
  const iso = log.captured_at ?? log.logged_at;
  return new Date(iso).toISOString().slice(0, 10);
}

export function groupMealLogsByDay(logs: MealLogOut[]): { day: string; entries: MealLogOut[] }[] {
  const byDay = new Map<string, MealLogOut[]>();
  for (const log of logs) {
    const key = dayKey(log);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(log);
  }

  const days = Array.from(byDay.keys()).sort((a, b) => (a < b ? 1 : -1)); // most recent first

  return days.map((day) => ({
    day,
    entries: byDay.get(day)!.slice().sort((a, b) => {
      const slotDiff = SLOT_ORDER[a.meal_slot] - SLOT_ORDER[b.meal_slot];
      if (slotDiff !== 0) return slotDiff;
      return new Date(a.logged_at).getTime() - new Date(b.logged_at).getTime();
    }),
  }));
}
```

```tsx
// frontend/src/components/meal-logs/MealCard.tsx
import { MEAL_SLOT_LABELS, type MealLogOut } from "@/lib/api/mealLogs";

const REACTION_EMOJI: Record<"happy" | "neutral" | "sad", string> = {
  happy: "😊", neutral: "😐", sad: "😞",
};

export function MealCard({
  meal, photoUrl, children,
}: {
  meal: MealLogOut;
  photoUrl: string;
  children?: React.ReactNode; // HC view slots its reaction-picker in here; client view passes nothing
}) {
  return (
    <div className="w-56 flex-shrink-0 space-y-2 rounded-md border border-border p-3">
      <img src={photoUrl} alt={meal.photo_original_filename} className="h-32 w-full rounded object-cover" />
      <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
        {MEAL_SLOT_LABELS[meal.meal_slot]}
      </p>
      {meal.description && <p className="font-sans text-sm text-foreground">{meal.description}</p>}
      <p className="font-sans text-xs text-muted-foreground">
        {meal.captured_at
          ? new Date(meal.captured_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : "Time not available"}
      </p>
      {meal.hc_reaction && <p className="text-lg">{REACTION_EMOJI[meal.hc_reaction]}</p>}
      {children}
    </div>
  );
}
```

- [ ] **Step 10.4: Run — confirm pass, then commit**

```bash
cd frontend && npx vitest run
git add frontend/src/components/meal-logs/ frontend/tests/unit/groupByDay.test.ts
git commit -m "feat(meal-logs): shared day-grouping helper + MealCard component (PHASE-03 Task 10)"
```

---

## Task 11: Frontend — HC-side "Logged Meals" sub-view inside `ChatTab`

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx` (`ChatTab` — **read PHASE-02b's and PHASE-02c's actual shipped version first, per this plan's top-of-file dependency callout, before touching this**)

**Interfaces:**
- Consumes: `listClientMealLogs`, `reactToMealLog`, `mealLogPhotoUrl` (Task 9), `groupMealLogsByDay`, `MealCard` (Task 10).
- Produces: a third `TabsTrigger`/`TabsContent` pair inside `ChatTab`, alongside PHASE-02c's Text and PHASE-02b's Check-ins.

- [ ] **Step 11.1: Add the third sub-tab**

**This step's exact diff depends on PHASE-02b/02c's real shipped `ChatTab` code**, which does not exist yet as of this plan being written (see top-of-file dependency callout). The shape assumed here, based on their plan documents: `ChatTab` holds `subTab` state and a `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` switcher with `"text"` and `"checkins"` values (PHASE-02c Task 5). Add a third value:

```tsx
        <TabsList variant="line">
          <TabsTrigger value="text">Text</TabsTrigger>
          <TabsTrigger value="checkins">Check-ins</TabsTrigger>
          <TabsTrigger value="meals">Logged Meals</TabsTrigger>
        </TabsList>
        {/* ...existing TabsContent for "text" and "checkins"... */}
        <TabsContent value="meals">
          <LoggedMealsView clientId={clientId} />
        </TabsContent>
```

If the real shipped `ChatTab` uses a different state/component shape, adapt this insertion point accordingly — the important thing this task must produce either way is a `LoggedMealsView` reachable as a third peer of Text/Check-ins.

- [ ] **Step 11.2: Implement `LoggedMealsView`**

```tsx
function LoggedMealsView({ clientId }: { clientId: string }) {
  const [mealLogs, setMealLogs] = useState<MealLogOut[] | null>(null);
  const [reacting, setReacting] = useState<string | null>(null); // meal log id currently being reacted to

  useEffect(() => {
    listClientMealLogs(clientId).then((data) => setMealLogs(data.items)).catch(() => setMealLogs([]));
  }, [clientId]);

  async function handleReact(mealLogId: string, reaction: "happy" | "neutral" | "sad") {
    setReacting(mealLogId);
    try {
      const updated = await reactToMealLog(clientId, mealLogId, reaction);
      setMealLogs((prev) => prev?.map((m) => (m.id === mealLogId ? updated : m)) ?? null);
    } finally {
      setReacting(null);
    }
  }

  if (mealLogs === null) return <p className="font-sans text-sm text-muted-foreground">Loading…</p>;
  if (mealLogs.length === 0) return <p className="font-sans text-sm italic text-muted-foreground">No meals logged yet.</p>;

  const groups = groupMealLogsByDay(mealLogs);

  return (
    <div className="space-y-8">
      {groups.map(({ day, entries }) => (
        <div key={day} className="space-y-3">
          <h3 className="font-heading text-sm font-bold text-foreground">
            {new Date(day).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
          </h3>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {entries.map((meal) => (
              <MealCard key={meal.id} meal={meal} photoUrl={mealLogPhotoUrl(clientId, meal.id)}>
                <div className="flex gap-1">
                  {(["happy", "neutral", "sad"] as const).map((r) => (
                    <button
                      key={r}
                      onClick={() => handleReact(meal.id, r)}
                      disabled={reacting === meal.id}
                      className={`rounded px-1.5 py-0.5 text-sm ${meal.hc_reaction === r ? "bg-primary/20" : ""}`}
                    >
                      {{ happy: "😊", neutral: "😐", sad: "😞" }[r]}
                    </button>
                  ))}
                </div>
              </MealCard>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

Add imports: `listClientMealLogs, reactToMealLog, mealLogPhotoUrl, type MealLogOut` from `@/lib/api/mealLogs`; `groupMealLogsByDay` from `@/components/meal-logs/groupByDay`; `MealCard` from `@/components/meal-logs/MealCard`.

- [ ] **Step 11.3: E2E — extend mocks + add a test**

Extend `frontend/tests/e2e/fixtures/mock-api.ts` with `/api/clients/{id}/meal-logs` GET/POST-react handlers; add a test clicking the "Logged Meals" sub-tab, asserting a day heading and a meal card render, clicking a reaction face, asserting it highlights.

- [ ] **Step 11.4: Run full frontend suite, then commit**

```bash
cd frontend && npx vitest run && npx playwright test
git add "frontend/src/app/(app)/clients/[clientId]/page.tsx" frontend/tests/e2e/
git commit -m "feat(client-detail): Logged Meals sub-view inside Chat tab, HC side (PHASE-03 Task 11, D-26)"
```

---

## Task 12: Frontend — client-facing meal-logging + history, nested in `/me/chat`

**Files:**
- Modify: `frontend/src/app/me/chat/page.tsx` (**read PHASE-02c's actual shipped version first — same dependency risk as Task 11**)

**Interfaces:**
- Consumes: `listMyMealLogs`, `submitMyMealLog`, `myMealLogPhotoUrl` (Task 9), `groupMealLogsByDay`, `MealCard` (Task 10).

- [ ] **Step 12.1: Add the third sub-tab to `/me/chat`**

Per D-31: "`/me/chat` ← messaging (D-25) + meal-logging (F3) nested inside, mirrors D-20's own Text/Check-ins/Logged Meals grouping." **This assumes PHASE-02c's `/me/chat/page.tsx` already has its own sub-tab switcher by the time this task runs** — if PHASE-02c shipped `/me/chat` as a single Text-only view with no switcher yet (plausible, since PHASE-02c's own plan only mentions Text), this task must *add* the switcher, not just a third branch of one. Check the real file before writing this diff.

Target shape (adapt to what's actually there):

```tsx
        <TabsList variant="line">
          <TabsTrigger value="text">Text</TabsTrigger>
          <TabsTrigger value="checkins">Check-ins</TabsTrigger>
          <TabsTrigger value="meals">Logged Meals</TabsTrigger>
        </TabsList>
        <TabsContent value="meals">
          <MyMealLogsView />
        </TabsContent>
```

- [ ] **Step 12.2: Implement `MyMealLogsView`**

```tsx
function MyMealLogsView() {
  const [mealLogs, setMealLogs] = useState<MealLogOut[] | null>(null);
  const [mealSlot, setMealSlot] = useState<MealSlot>("breakfast");
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMyMealLogs().then((data) => setMealLogs(data.items)).catch(() => setMealLogs([]));
  }, []);

  async function handleSubmit() {
    if (!photo) {
      setError("A photo is required to log a meal.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await submitMyMealLog({ mealSlot, description: description || undefined, photo });
      setMealLogs((prev) => [created, ...(prev ?? [])]);
      setDescription("");
      setPhoto(null);
    } catch {
      setError("Couldn't save that meal log. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const groups = mealLogs ? groupMealLogsByDay(mealLogs) : [];

  return (
    <div className="space-y-8">
      <div className="space-y-3 rounded-md border p-4">
        <p className="font-sans text-sm font-bold text-foreground">Log a meal</p>
        <div className="flex flex-wrap gap-2">
          {MEAL_SLOTS.map((slot) => (
            <button
              key={slot}
              onClick={() => setMealSlot(slot)}
              className={`rounded-full border px-3 py-1 font-sans text-xs ${
                mealSlot === slot ? "border-primary bg-primary text-primary-foreground" : "border-border text-foreground"
              }`}
            >
              {MEAL_SLOT_LABELS[slot]}
            </button>
          ))}
        </div>
        <input
          type="file" accept="image/jpeg,image/png,image/webp,image/heic" capture="environment"
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
          className="font-sans text-xs"
        />
        <textarea
          value={description} onChange={(e) => setDescription(e.target.value)}
          placeholder="What did you eat? (optional)"
          className="w-full rounded-md border border-border p-2 font-sans text-sm"
        />
        {error && <p className="font-sans text-sm text-destructive">{error}</p>}
        <Button onClick={handleSubmit} disabled={submitting || !photo}>
          {submitting ? "Saving…" : "Log meal"}
        </Button>
      </div>

      <div className="space-y-8">
        {mealLogs === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}
        {mealLogs !== null && mealLogs.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">No meals logged yet.</p>
        )}
        {groups.map(({ day, entries }) => (
          <div key={day} className="space-y-3">
            <h3 className="font-heading text-sm font-bold text-foreground">
              {new Date(day).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
            </h3>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {entries.map((meal) => (
                <MealCard key={meal.id} meal={meal} photoUrl={myMealLogPhotoUrl(meal.id)} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

Note on `capture="environment"`: this is the soft, non-blocking nudge described (not endorsed as sufficient) in Design Decision 1's anti-gaming discussion — it hints mobile browsers toward the live rear camera but does not prevent gallery selection, and has inconsistent support outside mobile Chrome/Safari. Included here as a harmless default, not as an implemented solution to the anti-gaming question.

Add imports: `listMyMealLogs, submitMyMealLog, myMealLogPhotoUrl, MEAL_SLOTS, MEAL_SLOT_LABELS, type MealLogOut, type MealSlot` from `@/lib/api/mealLogs`; `groupMealLogsByDay` from `@/components/meal-logs/groupByDay`; `MealCard` from `@/components/meal-logs/MealCard`; `Button` from `@/components/ui/button`.

- [ ] **Step 12.3: E2E test**

Add to a new or existing `/me/chat` e2e spec: mock `/api/me/meal-logs` GET/POST; visit `/me/chat`, switch to the "Logged Meals" sub-tab, attempt submit with no photo (assert the inline error), then submit with a photo attached (assert it appears under today's day group).

- [ ] **Step 12.4: Run full frontend suite, then commit**

```bash
cd frontend && npx vitest run && npx playwright test
git add frontend/src/app/me/chat/page.tsx frontend/tests/e2e/
git commit -m "feat(me): meal-logging + history nested in /me/chat, client side (PHASE-03 Task 12, D-26, D-31)"
```

---

## Task 13: DPDP deletion cascade verification

**Files:**
- Modify: `backend/tests/integration/test_clients.py` (extend, if a client-deletion cascade test already exists there — check first) or wherever the existing cascade-delete test for `check_ins`/`client_messages` lives

**Interfaces:**
- None new — this verifies Task 1's `ON DELETE CASCADE` foreign key actually fires, per CLAUDE.md §9 principle 8 ("deletion is real") and the spec's §7 compliance note ("when a client is deleted, cascade-delete... meal logs").

- [ ] **Step 13.1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_deleting_client_cascades_to_meal_logs(http_client, hc_headers, client_headers, client_rec, db):
    from unittest.mock import AsyncMock, patch
    import sqlalchemy as sa
    from src.db.models import MealLog

    with patch("src.api.me.s3_put", new_callable=AsyncMock), \
         patch("src.api.me.extract_capture_time", return_value=None):
        await http_client.post(
            "/api/me/meal-logs", headers=client_headers,
            data={"meal_slot": "breakfast"},
            files={"photo": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )

    await http_client.delete(f"/api/clients/{client_rec.id}", headers=hc_headers)

    remaining = (await db.execute(
        sa.select(MealLog).where(MealLog.client_id == client_rec.id)
    )).scalars().all()
    assert remaining == []
```

Note: this test does **not** verify the underlying S3 photo object is also deleted — `ON DELETE CASCADE` only removes the DB row, not the R2 object at `photo_storage_path`. Whether client deletion should also purge S3 objects (across every table that stores one — `client_files`, and now `meal_logs`) is a pre-existing gap this plan doesn't newly introduce or newly fix; flagging it in Self-review rather than silently scoping it into this task.

- [ ] **Step 13.2: Run — confirm failure, then implement if needed, then pass**

Run: `cd backend && pytest tests/integration/test_clients.py -k meal_log_cascade -v`. If Task 1's `ondelete="CASCADE"` FK is correct, this should pass with zero additional code — it's a verification task, not new logic.

- [ ] **Step 13.3: Full backend suite, then commit**

```bash
cd backend && pytest -x
git add backend/tests/integration/test_clients.py
git commit -m "test(meal-logs): verify DPDP deletion cascade for meal_logs (PHASE-03 Task 13)"
```

---

## Self-review

**Spec coverage (against F3 / D-26):**

| D-26 / F3 requirement | Covered by |
|---|---|
| Five fixed, ordered meal slots | Task 1 (`CHECK` constraint), Task 4 (validation), Task 9 (`MEAL_SLOTS` constant, shared by both frontends) |
| Photo mandatory | Task 4 (`photo: UploadFile = File(...)`, no optional path — FastAPI 422s automatically if omitted) |
| Capture-time from photo's own EXIF, basic effort only | Task 3 (`extract_capture_time`, JPEG/PNG/WebP via Pillow; HEIC and corrupt bytes degrade to `None`, never raise) |
| EXIF-missing / client-correction / anti-gaming left unresolved | Design Decision 1 — genuinely not resolved, only a working default (Decision 1a) implemented where code had to do *something* |
| Three-option HC reaction (happy/neutral/sad), supersedes D-4's thumbs-up | Task 5 (`react_to_meal_log`, `CHECK` constraint), Task 11 (reaction buttons) |
| Grouped by day, horizontally scrollable within a day, no rated/unrated split | Task 10 (`groupMealLogsByDay`), Tasks 11/12 (`overflow-x-auto` row per day) — the "no rated/unrated split" requirement is satisfied by construction: neither `LoggedMealsView` nor `MyMealLogsView` filters or partitions by `hc_reaction` anywhere |
| Real comment about a meal goes through Text, not inline | Not built here by omission — no comment/text field exists anywhere on `MealLog` or `MealCard`, matching D-4/D-26 exactly |
| D-24 passive Roster Board indicator | **Not built** — Design Decision 4, recommending a follow-on PHASE-03b once this phase's `reacted_at` exists alongside PHASE-02b/02c's own signal fields |

**Placeholder scan:** No TBD/TODO left as dead stubs. Two intentionally-incomplete pieces, both named as such rather than hidden: (1) Design Decision 1's missing-EXIF handling is a real, working default (`captured_at = NULL`, grouped by `logged_at` instead) explicitly flagged as provisional, not a placeholder; (2) `capture="environment"` in Task 12 is explicitly documented in-line as a non-solution to the anti-gaming question, included only as a harmless default.

**Type consistency:** `MealLogOut` defined once in `meal_logs.py` (Task 5), imported into `me.py` (Task 4) via the same cross-import convention as `CheckInOut`/`MessageOut` elsewhere in this codebase — no duplicate schema definition. Frontend `MealLogOutSchema` (Task 9) is the single shared source for both the HC (`ChatTab`) and client (`/me/chat`) views — `groupMealLogsByDay`/`MealCard` (Task 10) are written once and reused by both, not forked.

**Dependency risk (real, not a formality — restated from the top of this file):** This entire plan's frontend integration (Tasks 11, 12) assumes PHASE-02b's and PHASE-02c's `ChatTab`/`/me/chat` components match what their own *plan documents* describe — a `subTab` state variable, a `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` switcher with `"text"`/`"checkins"` values. **Neither has actually shipped as of this writing** (verified: no `ClientMessage` model, no `client_messages` table, live Alembic head is `c8af0b7b55f9`, predating both). If the real implementation differs — different state shape, a different tab library, `ChatTab` not yet having a switcher at all because PHASE-02c shipped Text as the sole content — Tasks 11 and 12's exact diffs will not apply cleanly and must be adapted to the real code, not forced to match this plan. This is the single largest execution risk in this plan and is not something a task-by-task TDD process will surface early: the backend tasks (1–8) have no dependency on PHASE-02b/02c at all and will pass in isolation regardless, so a false sense of "this plan is on track" is possible right up until Task 11 actually opens the real `page.tsx`.

**Known follow-ups (not silently dropped):**
- D-26's three explicitly-pinned questions (EXIF-missing behavior, client correction, anti-gaming) — Design Decision 1, genuinely awaiting SoJo.
- `meal_logs` schema gaps filled with provisional defaults — Design Decision 2 (description nullability, no slot/day uniqueness constraint, reaction overwritability) — please confirm or override each.
- D-24 Roster Board indicator — Design Decision 4, recommending PHASE-03b.
- Native HEIC EXIF support (`pillow-heif`) — Design Decision 5, deliberately not added.
- GPS EXIF stripping from stored photo bytes — Design Decision 6, a real compliance question, not resolved here.
- S3 object deletion on client-delete cascade (pre-existing gap, not newly introduced) — noted in Task 13.

**Execution:** Subagent-driven, per SoJo's standing instruction — no execution-choice question needed.
