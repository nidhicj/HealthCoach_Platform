"""HC-facing Lead test-recommendation review/send endpoints. Unit_003 PHASE-04
Task 5 — the first HC-authenticated Lead-management endpoints in this codebase.

GET /api/leads/:id/test-recommendation — HC reviews the AI-drafted test panel:
a Lead summary built from `LeadQuestionnaireResponse` rows plus
`leads.draft_test_recommendation` (written by Task 3's
`POST /api/intake/:slug`, PHASE-04 Stage 3).

POST /api/leads/:id/test-recommendation/send — HC finalizes the panel (with
their own edits to `additions`; the `standard` baseline is not editable here —
D-4) into `leads.test_recommendation`, and the Lead-facing email goes out
(Task 4's `send_finalized_test_recommendation_email`).
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models import Lead, LeadQuestionnaireResponse, User
from src.lib.email import send_finalized_test_recommendation_email
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/leads", tags=["leads"])


# ── schemas ────────────────────────────────────────────────────────────────────


class QuestionAnswerOut(BaseModel):
    question_key: str
    question_text: str
    response_text: str | None


class TestAdditionOut(BaseModel):
    test: str
    rationale: str


class TestRecommendationOut(BaseModel):
    standard: list[str]
    additions: list[TestAdditionOut]
    all_tests: list[str]


class LeadTestRecommendationOut(BaseModel):
    lead_id: UUID
    full_name: str
    email: str
    phone: str | None
    status: str
    questionnaire_responses: list[QuestionAnswerOut]
    # False when `leads.draft_test_recommendation` is still null — shouldn't be
    # reachable in practice (Task 3 always writes something, including its
    # AI-failure fallback, before the HC review email fires) but this endpoint
    # must return a structured response instead of crashing if it happens.
    ready: bool
    draft_test_recommendation: TestRecommendationOut | None = None
    # Non-null once the HC has already Sent a panel for this Lead
    # (`leads.test_recommendation`) — the review screen link stays live in the
    # HC's inbox indefinitely, so reopening it after a Send must let the
    # frontend seed its editor from the already-sent panel, not silently
    # discard it in favor of the original AI draft. See final-review-fix
    # round Fix #1.
    test_recommendation: TestRecommendationOut | None = None


class TestAdditionIn(BaseModel):
    test: str = Field(max_length=200)
    rationale: str = Field(max_length=2000)

    @field_validator("test")
    @classmethod
    def _test_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("test name cannot be blank")
        return v.strip()


class SendTestRecommendationIn(BaseModel):
    """The HC's edited `additions` list. `standard` is deliberately absent —
    it's not editable here (D-4); it's the HC's Test Panel setting, carried
    over verbatim from the draft this Lead already has."""
    additions: list[TestAdditionIn] = Field(max_length=50)


class SendTestRecommendationOut(BaseModel):
    lead_id: UUID
    status: str
    test_recommendation: TestRecommendationOut


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/{lead_id}/test-recommendation")
async def get_test_recommendation(
    lead_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> LeadTestRecommendationOut:
    lead = await _get_owned_lead(db, lead_id, hc_id)

    # No ORDER BY — mirrors src.llm_service's own query for these exact rows
    # (generate_lead_test_recommendation / generate_lead_brief).
    # LeadQuestionnaireResponse has no explicit sequence column, and
    # `submitted_at` is a single `now()` shared by every row from one
    # questionnaire submission (same DB transaction), so it can't be used as
    # a submission-order tiebreaker either — this is the established
    # convention for these rows, not an oversight.
    q_rows = (await db.execute(
        select(LeadQuestionnaireResponse).where(LeadQuestionnaireResponse.lead_id == lead.id)
    )).scalars().all()

    draft = lead.draft_test_recommendation
    return LeadTestRecommendationOut(
        lead_id=lead.id,
        full_name=lead.full_name,
        email=lead.email,
        phone=lead.phone,
        status=lead.status,
        questionnaire_responses=[
            QuestionAnswerOut(
                question_key=r.question_key,
                question_text=r.question_text,
                response_text=r.response_text,
            )
            for r in q_rows
        ],
        ready=draft is not None,
        draft_test_recommendation=TestRecommendationOut(**draft) if draft is not None else None,
        test_recommendation=(
            TestRecommendationOut(**lead.test_recommendation)
            if lead.test_recommendation is not None
            else None
        ),
    )


def _draft_not_ready_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "draft_not_ready",
            "message": "This Lead's AI-drafted test recommendation isn't ready yet.",
        },
    )


def _status_not_reviewable_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "status_not_reviewable",
            "message": "This Lead has moved past the test-recommendation review stage.",
        },
    )


@router.post("/{lead_id}/test-recommendation/send", status_code=status.HTTP_201_CREATED)
async def send_test_recommendation(
    lead_id: UUID,
    body: SendTestRecommendationIn,
    request: Request,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> SendTestRecommendationOut:
    """Finalizes the HC's (possibly edited) test panel and emails the Lead.

    Idempotency (deliberate choice, not a default left unconsidered): calling
    this twice for the same Lead — a double-click, or a genuine second Send —
    is ALLOWED, not blocked. Each call overwrites `leads.test_recommendation`
    with whatever `additions` are submitted on that call and re-sends the
    finalized-panel email. Reasoning: there is no stated product rule that a
    Lead's panel is immutable once sent, and the HC may legitimately need to
    correct a mistake after the first Send (a typo in a test name, a test that
    should be dropped) — the review screen this endpoint serves is explicitly
    editable, so re-submitting an edit and re-sending is the expected repair
    path, not an error condition. This also mirrors this codebase's existing
    convention of no already-sent guard on repeatable finalize "/send"
    actions: `POST /api/clients/:id/diet-chart/send` (diet_charts.py) can be
    called any number of times — each call inserts a fresh `DietChartSend`
    row recording the send event, with nothing blocking a repeat (the
    endpoint itself does not send an email; it only persists the record) —
    and `POST /api/clients/:id/invite` (clients.py) likewise rejects nothing
    on a second call: it invalidates the previous invite token and issues a
    new one (returned to the caller; the endpoint itself does not email it
    either). Neither precedent involves the endpoint sending an email on
    repeat — the part of the precedent that actually applies here is that
    repeating a finalize-style action is the established, unguarded pattern
    in this codebase, which is what justifies allowing double-Send above.
    `status_code=201` on this route mirrors `send_client_diet_chart`'s status
    code for the same shape of action.
    """
    lead = await _get_owned_lead(db, lead_id, hc_id)

    if lead.draft_test_recommendation is None:
        raise _draft_not_ready_error()

    # `leads.status` is documented (SPEC-0001 Data section) as one-way through
    # a fixed enum. Repeated sends while still at `tests_drafted` or
    # `tests_recommended` are the deliberate double-Send allowance described
    # in this function's docstring above — that is unaffected by this guard.
    # A Lead that has moved on to a later stage (payment, scheduling, report
    # upload, etc. — not reachable yet, but will be once PHASE-05 ships) must
    # not have its status walked backward to `tests_recommended` by a stale
    # review-screen link still sitting in the HC's inbox.
    if lead.status not in {"tests_drafted", "tests_recommended"}:
        raise _status_not_reviewable_error()

    # `standard` is carried over verbatim from the draft Task 3 already wrote
    # for this Lead — never re-read fresh from `hc_leadgen_config.test_panel`,
    # which may have changed since the draft was generated. The baseline is
    # not part of the HC's edit payload here (D-4); it's a separate Test Panel
    # setting owned elsewhere in the app.
    standard_tests: list[str] = list(lead.draft_test_recommendation.get("standard") or [])

    additions_data = [{"test": a.test, "rationale": a.rationale} for a in body.additions]

    # Same dedup discipline as Task 3's POST /api/intake/:slug (src/api/intake.py):
    # start from the standard baseline, then append each addition's test name
    # only if not already present — first-seen order preserved.
    all_tests = list(standard_tests)
    for addition in additions_data:
        test = addition["test"]
        if test not in all_tests:
            all_tests.append(test)

    test_recommendation = {
        "standard": standard_tests,
        "additions": additions_data,
        "all_tests": all_tests,
    }
    lead.test_recommendation = test_recommendation
    lead.status = "tests_recommended"
    await db.commit()

    hc_user = await db.get(User, UUID(hc_id))
    hc_first = (hc_user.first_name if hc_user else None) or ""
    hc_last = (hc_user.last_name if hc_user else None) or ""
    # Fallback guards against a blank/double-space artifact in
    # send_finalized_test_recommendation_email's copy (src/lib/email.py) if
    # both names are unset. Unreachable today — Stage 1 leadgen setup gates
    # on both first/last name being present (PHASE-01/PHASE-06) — but cheap
    # to guard. "Your Coach" (not "Your health coach") deliberately avoids a
    # literal duplicate where the template already reads "Your health coach,
    # {hc_name}, recommends..." — substituting "Your health coach" there
    # would repeat the phrase back to back.
    hc_name = f"{hc_first} {hc_last}".strip() or "Your Coach"

    # Non-blocking — matches this codebase's established convention for
    # outbound email that must never fail the primary action (see
    # src/api/intake.py's own call to send_test_recommendation_review_email,
    # and src/api/upload.py's calls to send_lead_brief_ready_email /
    # send_lead_brief_failed_email): the primary action — finalizing and
    # durably persisting `leads.test_recommendation` — is already committed
    # above, so a failure to email the Lead must not turn this into an error
    # response for the HC.
    logger = get_logger(request_id=getattr(request.state, "request_id", ""), hc_id=hc_id)
    try:
        send_finalized_test_recommendation_email(
            to=lead.email,
            lead_name=lead.full_name,
            hc_name=hc_name,
            test_list=all_tests,
        )
    except Exception as exc:
        logger.error(
            "finalized_test_recommendation_email_failed", lead_id=str(lead.id), error=str(exc)
        )

    return SendTestRecommendationOut(
        lead_id=lead.id,
        status=lead.status,
        test_recommendation=TestRecommendationOut(**test_recommendation),
    )


# ── shared helper ──────────────────────────────────────────────────────────────


async def _get_owned_lead(db: DbDep, lead_id: UUID, hc_id: str) -> Lead:
    row = (await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return row
