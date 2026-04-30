"""Structured JSON logger per ADR-0006 §2. Binds request_id/user_id/hc_id/role."""
import json
from datetime import datetime, timezone
from typing import Any

from .scrub import scrub


class BoundLogger:
    def __init__(self, request_id: str, user_id: str | None,
                 hc_id: str | None, role: str) -> None:
        self._base: dict[str, Any] = {
            "request_id": request_id,
            "user_id": user_id,
            "hc_id": hc_id,
            "role": role,
        }

    def _emit(self, level: str, event: str, extra: dict[str, Any] | None = None) -> None:
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            **self._base,
        }
        if extra:
            record["extra"] = extra
        print(json.dumps(scrub(record)))

    def info(self, event: str, **extra: Any) -> None:
        self._emit("info", event, extra or None)

    def warn(self, event: str, **extra: Any) -> None:
        self._emit("warn", event, extra or None)

    def error(self, event: str, **extra: Any) -> None:
        self._emit("error", event, extra or None)


def get_logger(
    request_id: str,
    user_id: str | None = None,
    hc_id: str | None = None,
    role: str = "anon",
) -> BoundLogger:
    return BoundLogger(request_id, user_id, hc_id, role)
