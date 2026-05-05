"""Builds OpenRouter models array from llm_config. Per ADR-0003 §3."""
from __future__ import annotations

from src.llm_service.config import LLMConfig, get_llm_config


def build_models_array(config: LLMConfig | None = None) -> list[str]:
    """Return the full model chain for the OpenRouter `models` array parameter."""
    cfg = config or get_llm_config()
    return list(cfg.model_chain)


def fallback_count_for(model_served: str, config: LLMConfig | None = None) -> int:
    """
    Index of model_served in the chain = how many fallbacks occurred.
    Returns -1 if model_served is not in our chain (OpenRouter chose outside it).
    """
    cfg = config or get_llm_config()
    try:
        return cfg.model_chain.index(model_served)
    except ValueError:
        return -1
