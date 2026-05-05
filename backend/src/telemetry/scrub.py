"""PII scrubber for Sentry events and structured log lines. Per ADR-0006 §3."""
import re
from typing import Any

_PII_KEYS = frozenset({
    "email", "phone", "name", "full_name", "display_name",
    "password", "token", "secret", "authorization", "cookie",
    "transcript", "transcript_content", "mom_content", "snippet_content",
    "original_text", "hc_modified_text", "refresh_token",
    "prompt_text", "completion_text",
})

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _truncate_ip(ip: str) -> str:
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:3]) + "::"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
    return ip


def _scrub_value(key: str, value: Any) -> Any:
    if key.lower() in _PII_KEYS:
        return "<redacted>"
    if key.lower() == "ip" and isinstance(value, str):
        return _truncate_ip(value)
    if isinstance(value, str):
        value = _JWT_RE.sub("<jwt_redacted>", value)
        value = _EMAIL_RE.sub("<email_redacted>", value)
    return value


def scrub(obj: Any) -> Any:
    """Recursively scrub PII from a dict/list/str. Safe to call on Sentry events."""
    if isinstance(obj, dict):
        return {k: _scrub_value(k, scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(item) for item in obj]
    return obj
