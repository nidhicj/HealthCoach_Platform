"""SQLAlchemy TypeDecorator: transparently encrypt/decrypt a JSON dict using Fernet."""
import json

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

# Used when DEMOGRAPHICS_ENCRYPTION_KEY is absent (dev / test environments only).
# Not secure — production must set the env var.
_DEV_FALLBACK_KEY = b"ZGV2LXRlc3Qta2V5LTMyLWJ5dGVzLWV4YWN0bHkhISE="


def _fernet() -> Fernet:
    from src.config import get_settings
    raw = get_settings().demographics_encryption_key
    key = raw.encode() if raw else _DEV_FALLBACK_KEY
    return Fernet(key)


class EncryptedJSON(TypeDecorator):
    """Store a Python dict as Fernet-encrypted JSON in a TEXT column."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet().encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return json.loads(_fernet().decrypt(value.encode()))
        except (InvalidToken, Exception):
            # Graceful degradation: return None rather than crash the whole response
            # if ciphertext is corrupt or the key was rotated without re-encryption.
            return None
