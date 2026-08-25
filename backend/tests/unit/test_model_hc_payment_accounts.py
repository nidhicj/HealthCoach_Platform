"""Unit test: HcPaymentAccount model — columns, types, constraints. PHASE-05 Task 1."""
from src.db.encrypted_json import EncryptedJSON
from src.db.models.payments import HcPaymentAccount


def test_hc_payment_account_columns():
    cols = HcPaymentAccount.__table__.columns
    assert cols["hc_user_id"].nullable is False
    assert cols["hc_user_id"].unique is True
    assert cols["credentials"].nullable is True
    assert cols["connected_at"].nullable is True
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_hc_payment_account_hc_user_id_cascades_on_user_delete():
    fk = next(iter(HcPaymentAccount.__table__.columns["hc_user_id"].foreign_keys))
    assert fk.ondelete == "CASCADE"
    assert fk.column.table.name == "users"


def test_hc_payment_account_credentials_uses_dedicated_encryption_key():
    col_type = HcPaymentAccount.__table__.columns["credentials"].type
    assert isinstance(col_type, EncryptedJSON)
    assert col_type._settings_key == "razorpay_credentials_encryption_key"
