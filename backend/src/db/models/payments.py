"""Payment provider connection models. PHASE-05 (payment + scheduling handoff).

Concern-based file per llm.py's precedent — payment-provider concerns don't belong
in leadgen.py even though the connect/pay/webhook flow they support starts there.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.encrypted_json import EncryptedJSON


class HcPaymentAccount(Base):
    """One row per HC. Holds their Razorpay credentials, Fernet-encrypted at rest.

    `credentials` is nullable (unlike GoogleCalendarConnection's, which is populated
    atomically by an OAuth exchange): a row may exist before a working key pair is on
    file — e.g. the HC-facing connect endpoint (Task 2) can create the row first and
    fill `credentials` only once `razorpay_client.verify_credentials()` confirms the
    pair is valid. `connected_at` (also nullable) marks the moment credentials were
    last successfully verified and stored.
    """

    __tablename__ = "hc_payment_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    credentials: Mapped[dict | None] = mapped_column(
        EncryptedJSON(settings_key="razorpay_credentials_encryption_key")
    )
    connected_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
