"""Sentry initialization per ADR-0006 §1. Pyodide-compat: graceful no-op if SDK missing."""
import os
from typing import Any

from .scrub import scrub

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
        return scrub(event)  # type: ignore[return-value]

    def _before_breadcrumb(
        breadcrumb: dict[str, Any], hint: dict[str, Any]
    ) -> dict[str, Any] | None:
        return scrub(breadcrumb)  # type: ignore[return-value]

    def init_sentry() -> None:
        dsn = os.getenv("SENTRY_DSN", "")
        if not dsn:
            return
        try:
            sentry_sdk.init(
                dsn=dsn,
                environment=os.getenv("APP_ENV", "dev"),
                release=os.getenv("APP_VERSION", "0.1.0"),
                traces_sample_rate=0.0,
                profiles_sample_rate=0.0,
                send_default_pii=False,
                before_send=_before_send,
                before_breadcrumb=_before_breadcrumb,
                integrations=[StarletteIntegration(), FastApiIntegration()],
            )
        except Exception:
            pass

except ImportError:
    def init_sentry() -> None:  # type: ignore[misc]
        pass
