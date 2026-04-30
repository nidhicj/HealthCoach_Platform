"""P1.4 — roundtrip write/read for every table + cascade-delete assertions."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    ActionItem, AuditLog, AuthRefreshToken, Brief, CheckIn, Client,
    Consent, ContentAssignment, DietChart, DietChartRecipe, HcStyleSnippet,
    LlmCall, Mom, PrepRecipe, Session, User,
)

NOW = datetime.now(timezone.utc)


# ── helpers ──────────────────────────────────────────────────────────────────

async def _make_user(db: AsyncSession, **kw) -> User:  # type: ignore[return]
    u = User(email=kw.get("email", f"hc_{uuid4().hex[:6]}@test.com"),
             google_sub=kw.get("google_sub", uuid4().hex))
    db.add(u)
    await db.flush()
    return u


async def _make_client(db: AsyncSession, hc: User, **kw) -> Client:  # type: ignore[return]
    c = Client(hc_user_id=hc.id, full_name=kw.get("full_name", "Test Client"))
    db.add(c)
    await db.flush()
    return c


async def _make_session(db: AsyncSession, hc: User, client: Client, num: int = 1) -> Session:
    s = Session(hc_user_id=hc.id, client_id=client.id,
                session_number=num, scheduled_at=NOW)
    db.add(s)
    await db.flush()
    return s


async def _make_llm_call(db: AsyncSession, hc: User, session: Session | None = None) -> LlmCall:
    lc = LlmCall(
        hc_user_id=hc.id, session_id=session.id if session else None,
        use_case="test", prompt_version="test_v1",
        model_requested="test-model", input_tokens=10, output_tokens=20, latency_ms=100,
    )
    db.add(lc)
    await db.flush()
    return lc


# ── roundtrip tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_roundtrip(db: AsyncSession) -> None:
    u = await _make_user(db, email="roundtrip@test.com")
    await db.commit()
    result = await db.get(User, u.id)
    assert result is not None
    assert result.email == "roundtrip@test.com"


@pytest.mark.asyncio
async def test_client_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc, full_name="Jane Doe")
    await db.commit()
    result = await db.get(Client, client.id)
    assert result is not None
    assert result.full_name == "Jane Doe"
    assert result.journey_stage == "onboarding"


@pytest.mark.asyncio
async def test_session_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    sess = await _make_session(db, hc, client, num=0)
    await db.commit()
    result = await db.get(Session, sess.id)
    assert result is not None
    assert result.session_number == 0


@pytest.mark.asyncio
async def test_llm_call_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    lc = await _make_llm_call(db, hc)
    await db.commit()
    result = await db.get(LlmCall, lc.id)
    assert result is not None
    assert result.use_case == "test"
    assert result.model_requested == "test-model"
    assert result.model_served is None


@pytest.mark.asyncio
async def test_mom_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    sess = await _make_session(db, hc, client)
    lc = await _make_llm_call(db, hc, sess)
    mom = Mom(session_id=sess.id, hc_user_id=hc.id, client_id=client.id,
              draft_text="Draft MOM", llm_call_id=lc.id)
    db.add(mom)
    await db.commit()
    result = await db.get(Mom, mom.id)
    assert result is not None
    assert result.status == "draft"
    assert result.draft_text == "Draft MOM"


@pytest.mark.asyncio
async def test_brief_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    sess = await _make_session(db, hc, client)
    brief = Brief(session_id=sess.id, hc_user_id=hc.id, client_id=client.id,
                  brief_text="Pre-session brief")
    db.add(brief)
    await db.commit()
    result = await db.get(Brief, brief.id)
    assert result is not None
    assert result.brief_text == "Pre-session brief"


@pytest.mark.asyncio
async def test_action_item_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    item = ActionItem(client_id=client.id, hc_user_id=hc.id, description="Drink 2L water daily")
    db.add(item)
    await db.commit()
    result = await db.get(ActionItem, item.id)
    assert result is not None
    assert result.status == "open"


@pytest.mark.asyncio
async def test_check_in_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    ci = CheckIn(client_id=client.id, hc_user_id=hc.id, payload={"mood": 7, "weight": 68.5})
    db.add(ci)
    await db.commit()
    result = await db.get(CheckIn, ci.id)
    assert result is not None
    assert result.payload["mood"] == 7


@pytest.mark.asyncio
async def test_hc_style_snippet_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    snippet = HcStyleSnippet(
        hc_user_id=hc.id, client_id=client.id,
        snippet_type="edit", original_text="AI draft", hc_modified_text="HC version",
    )
    db.add(snippet)
    await db.commit()
    result = await db.get(HcStyleSnippet, snippet.id)
    assert result is not None
    assert result.use_count == 0
    assert result.retired_at is None


@pytest.mark.asyncio
async def test_consent_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    consent = Consent(client_id=client.id, hc_user_id=hc.id,
                      purpose="ai_drafting", granted=True, granted_at=NOW, source="in_app")
    db.add(consent)
    await db.commit()
    result = await db.get(Consent, consent.id)
    assert result is not None
    assert result.granted is True


@pytest.mark.asyncio
async def test_audit_log_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    entry = AuditLog(actor_user_id=hc.id, action="read", target_table="clients")
    db.add(entry)
    await db.commit()
    result = await db.get(AuditLog, entry.id)
    assert result is not None
    assert result.action == "read"


@pytest.mark.asyncio
async def test_auth_refresh_token_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    from datetime import timedelta
    token = AuthRefreshToken(
        user_id=hc.id, token_hash="sha256hexhash",
        expires_at=NOW + timedelta(days=30),
    )
    db.add(token)
    await db.commit()
    result = await db.get(AuthRefreshToken, token.id)
    assert result is not None
    assert result.revoked_at is None


@pytest.mark.asyncio
async def test_diet_chart_and_recipe_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    chart = DietChart(hc_user_id=hc.id, name="Weight loss plan")
    recipe = PrepRecipe(hc_user_id=hc.id, name="Dal", ingredients={"dal": "100g", "water": "300ml"})
    db.add_all([chart, recipe])
    await db.flush()
    join = DietChartRecipe(diet_chart_id=chart.id, prep_recipe_id=recipe.id)
    db.add(join)
    await db.commit()
    result = await db.get(DietChart, chart.id)
    assert result is not None
    assert result.name == "Weight loss plan"


@pytest.mark.asyncio
async def test_content_assignment_roundtrip(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    chart = DietChart(hc_user_id=hc.id, name="Plan A")
    db.add(chart)
    await db.flush()
    assignment = ContentAssignment(
        hc_user_id=hc.id, client_id=client.id,
        content_type="diet_chart", content_id=chart.id,
    )
    db.add(assignment)
    await db.commit()
    result = await db.get(ContentAssignment, assignment.id)
    assert result is not None
    assert result.content_type == "diet_chart"


# ── cascade delete tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cascade_delete_client_removes_all_child_rows(db: AsyncSession) -> None:
    hc = await _make_user(db)
    client = await _make_client(db, hc)
    sess = await _make_session(db, hc, client)

    # Add one child of each client-scoped table
    db.add_all([
        Mom(session_id=sess.id, hc_user_id=hc.id, client_id=client.id, draft_text="x"),
        Brief(session_id=sess.id, hc_user_id=hc.id, client_id=client.id, brief_text="y"),
        ActionItem(client_id=client.id, hc_user_id=hc.id, description="z"),
        CheckIn(client_id=client.id, hc_user_id=hc.id, payload={}),
        HcStyleSnippet(hc_user_id=hc.id, client_id=client.id, snippet_type="edit", original_text="t"),
        Consent(client_id=client.id, hc_user_id=hc.id, purpose="service",
                granted=True, granted_at=NOW, source="in_app"),
    ])
    await db.flush()
    client_id = client.id
    await db.commit()

    # Delete the client
    c = await db.get(Client, client_id)
    await db.delete(c)
    await db.commit()

    # All child rows must be gone
    for model in (Mom, Brief, ActionItem, CheckIn, HcStyleSnippet, Consent, Session):
        rows = (await db.execute(
            select(model).where(model.client_id == client_id)  # type: ignore[attr-defined]
        )).scalars().all()
        assert rows == [], f"Expected no {model.__tablename__} rows after client delete"


@pytest.mark.asyncio
async def test_cascade_delete_user_removes_refresh_tokens(db: AsyncSession) -> None:
    from datetime import timedelta
    hc = await _make_user(db)
    token = AuthRefreshToken(
        user_id=hc.id, token_hash=f"hash_{uuid4().hex}",
        expires_at=NOW + timedelta(days=30),
    )
    db.add(token)
    await db.flush()
    user_id = hc.id
    await db.commit()

    u = await db.get(User, user_id)
    await db.delete(u)
    await db.commit()

    rows = (await db.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.user_id == user_id)
    )).scalars().all()
    assert rows == []
