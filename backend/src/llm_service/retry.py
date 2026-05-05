"""One validation retry with a stricter format hint. Per ADR-0003 §3."""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

STRICT_FORMAT_HINT = (
    "\n\nCRITICAL: Your previous response could not be parsed. "
    "Return ONLY valid JSON. No markdown fences, no explanation, no trailing text. "
    "The JSON must exactly match the requested schema."
)


async def parse_or_retry(
    raw: str,
    schema_cls: type[T],
    retry_fn: Callable[[], Awaitable[str]],
) -> tuple[T | None, bool, str | None]:
    """
    Try to parse raw against schema_cls. On failure, call retry_fn() and try once more.
    Returns (parsed_model | None, validation_failed, error_message).
    """
    try:
        return schema_cls.model_validate(json.loads(raw)), False, None
    except (json.JSONDecodeError, ValidationError, Exception):
        pass

    try:
        raw2 = await retry_fn()
        return schema_cls.model_validate(json.loads(raw2)), False, None
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        return None, True, str(e)
