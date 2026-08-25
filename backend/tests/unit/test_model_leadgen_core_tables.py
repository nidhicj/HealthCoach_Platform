"""Unit test: Lead, LeadQuestionnaireResponse, LeadUploadToken, LeadFile — columns and constraints."""
from src.db.models.leadgen import Lead, LeadFile, LeadQuestionnaireResponse, LeadUploadToken


def test_lead_columns():
    cols = Lead.__table__.columns
    assert cols["hc_user_id"].nullable is False
    assert cols["full_name"].nullable is False
    assert cols["email"].nullable is False
    assert cols["status"].nullable is False
    assert cols["converted_client_id"].nullable is True


def test_lead_unique_hc_email_constraint():
    constraint_cols = {tuple(c.columns.keys()) for c in Lead.__table__.constraints if hasattr(c, "columns") and len(c.columns) == 2}
    assert ("hc_user_id", "email") in constraint_cols


def test_lead_questionnaire_response_cascades_from_lead():
    fk = next(iter(LeadQuestionnaireResponse.__table__.columns["lead_id"].foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_lead_upload_token_hash_unique():
    assert LeadUploadToken.__table__.columns["token_hash"].unique is True


def test_lead_upload_token_expires_at_nullable():
    """PHASE-05 Task 3 / SPEC-0001 D-8: expires_at is NULL from Stage 3
    Send-time until leads.payment_status flips to paid — no longer NOT NULL."""
    assert LeadUploadToken.__table__.columns["expires_at"].nullable is True


def test_lead_payment_scheduling_columns():
    """PHASE-05 Task 3: five new leads columns, verbatim from SPEC-0001's
    §Data section for the leads table."""
    cols = Lead.__table__.columns
    assert cols["payment_status"].nullable is False
    assert cols["payment_status"].default.arg == "unpaid"
    assert cols["payment_reference"].nullable is True
    assert cols["paid_at"].nullable is True
    assert cols["scheduled_at"].nullable is True
    assert cols["meeting_link"].nullable is True


def test_lead_file_has_direct_tenant_scoping():
    cols = LeadFile.__table__.columns
    assert "hc_user_id" in cols  # direct scoping, not solely via lead join — per spec
