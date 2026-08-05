"""SQLAlchemy TypeDecorator: transparently encrypt/decrypt a JSON dict using Fernet."""
import json

import structlog
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = structlog.get_logger(__name__)

# Used when an encryption key is absent (dev / test environments only).
# Not secure — production must set the env var.
_DEV_FALLBACK_KEY = b"ZGV2LXRlc3Qta2V5LTMyLWJ5dGVzLWV4YWN0bHkhISE="


def _fernet(settings_key: str) -> Fernet:
    """Load a Fernet cipher from settings.

    Args:
        settings_key: The name of the settings attribute to read (e.g., 'demographics_encryption_key')

    Returns:
        A Fernet instance using the key from settings, or fallback key if settings key is empty.
    """
    from src.config import get_settings
    raw = getattr(get_settings(), settings_key)
    key = raw.encode() if raw else _DEV_FALLBACK_KEY
    return Fernet(key)


class EncryptedJSON(TypeDecorator):
    """Store a Python dict as Fernet-encrypted JSON in a TEXT column.

    Args:
        settings_key: The name of the settings attribute to read for the encryption key.
                     Defaults to 'demographics_encryption_key' for backwards compatibility.
    """

    impl = Text
    cache_ok = True

    def __init__(self, settings_key: str = "demographics_encryption_key", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._settings_key = settings_key

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet(self._settings_key).encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return json.loads(_fernet(self._settings_key).decrypt(value.encode()))
        except Exception:
            # Graceful degradation: return None rather than crash the whole response
            # if ciphertext is corrupt or the key was rotated without re-encryption.
            logger.warning("encrypted_json_decrypt_failed", settings_key=self._settings_key, exc_info=True)
            return None
