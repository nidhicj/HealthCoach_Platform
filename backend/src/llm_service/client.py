"""OpenRouter HTTP wrapper. All LLM HTTP calls go through here. Per ADR-0003 §3."""
from __future__ import annotations

import time
from dataclasses import dataclass

from src.config import get_settings
from src.lib.http import make_http_client  # patched in tests via src.llm_service.client.make_http_client

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class OpenRouterResult:
    content: str
    model_served: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw_request_id: str | None


async def call_openrouter(
    *,
    models: list[str],
    system_prompt: str,
    user_message: str,
    no_training: bool = True,
    no_retention: bool = True,
) -> OpenRouterResult:
    """
    POST to OpenRouter using the models array for built-in fallback.
    Raises httpx.HTTPStatusError on 4xx/5xx.
    """
    settings = get_settings()
    headers: dict[str, str] = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if no_training:
        headers["X-OR-Disable-Training"] = "true"
    if no_retention:
        headers["X-Data-Retention"] = "false"

    payload = {
        "models": models,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    # Free models can take 30–60 s; httpx default is 5 s which silently times out.
    t0 = time.monotonic()
    async with make_http_client(timeout=120.0) as http:
        resp = await http.post(OPENROUTER_URL, json=payload, headers=headers)
        resp.raise_for_status()
    latency_ms = int((time.monotonic() - t0) * 1000)

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    model_served = data.get("model", models[0])
    usage = data.get("usage", {})

    return OpenRouterResult(
        content=content,
        model_served=model_served,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency_ms,
        raw_request_id=data.get("id"),
    )
