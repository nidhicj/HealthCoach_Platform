"""Unit tests for EncryptedJSON TypeDecorator. Per task 1 of PHASE-01e."""
import pytest
from cryptography.fernet import Fernet

from src.db.encrypted_json import EncryptedJSON


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Fixture to guarantee cache cleanup after each test, even on assertion failure."""
    yield
    from src.config import get_settings
    get_settings.cache_clear()


def test_default_settings_key_is_demographics(monkeypatch):
    """Verify that the default constructor reads demographics_encryption_key."""
    # Set up a known test key
    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("DEMOGRAPHICS_ENCRYPTION_KEY", test_key)

    # Must clear cache after monkeypatching env
    from src.config import get_settings
    get_settings.cache_clear()

    # Default constructor should use demographics_encryption_key
    col = EncryptedJSON()
    encrypted = col.process_bind_param({"a": 1}, None)
    assert col.process_result_value(encrypted, None) == {"a": 1}


def test_custom_settings_key_round_trips(monkeypatch):
    """Verify that a custom settings_key parameter works correctly."""
    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("GOOGLE_CALENDAR_ENCRYPTION_KEY", test_key)

    from src.config import get_settings
    get_settings.cache_clear()

    col = EncryptedJSON(settings_key="google_calendar_encryption_key")
    encrypted = col.process_bind_param({"token": "abc"}, None)
    assert col.process_result_value(encrypted, None) == {"token": "abc"}


def test_cross_key_decrypt_fails_gracefully(monkeypatch):
    """Verify that ciphertext from one key cannot be decrypted by another key."""
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()

    monkeypatch.setenv("DEMOGRAPHICS_ENCRYPTION_KEY", key_a)
    monkeypatch.setenv("GOOGLE_CALENDAR_ENCRYPTION_KEY", key_b)

    from src.config import get_settings
    get_settings.cache_clear()

    # Encrypt with key_a
    col_a = EncryptedJSON()  # uses demographics_encryption_key (key_a)
    encrypted = col_a.process_bind_param({"secret": "x"}, None)

    # Try to decrypt with key_b — should return None gracefully
    col_b = EncryptedJSON(settings_key="google_calendar_encryption_key")
    result = col_b.process_result_value(encrypted, None)

    # Cross-key decryption should fail gracefully and return None
    assert result is None


def test_none_values_pass_through():
    """Verify that None values are handled correctly."""
    col = EncryptedJSON()

    # Binding None should return None
    encrypted = col.process_bind_param(None, None)
    assert encrypted is None

    # Decoding None should return None
    result = col.process_result_value(None, None)
    assert result is None


def test_fallback_key_used_when_env_empty(monkeypatch):
    """Verify that fallback key is used when the env var is empty."""
    monkeypatch.setenv("DEMOGRAPHICS_ENCRYPTION_KEY", "")

    from src.config import get_settings
    get_settings.cache_clear()

    # Should use fallback key, not crash
    col = EncryptedJSON()
    encrypted = col.process_bind_param({"data": "test"}, None)
    result = col.process_result_value(encrypted, None)
    assert result == {"data": "test"}
