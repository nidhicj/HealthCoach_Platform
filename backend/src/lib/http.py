"""HTTP client factory. Sets User-Agent on every client (workers-py #68 requirement)."""
import httpx

from src.config import get_settings

_UA = "parivarthan-backend/{version} (+https://github.com/poshini/parivarthan-platform)"


def make_http_client(**kwargs: object) -> httpx.AsyncClient:
    version = get_settings().app_version
    headers = {"User-Agent": _UA.format(version=version)}
    if "headers" in kwargs:
        headers = {**headers, **kwargs.pop("headers")}  # type: ignore[arg-type]
    return httpx.AsyncClient(headers=headers, **kwargs)
