"""Loads llm_config.yaml and exports LLMConfig. Per ADR-0003 §1."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class LLMConfig:
    model_chain: list[str]
    reasoning_model: str
    no_training_header: bool
    no_retention_header: bool
    snippet_pool_size: int
    snippet_diff_threshold: int
    snippet_whitespace_filter: bool
    snippet_token_budget: int
    snippet_max_count: int
    validation_retry_count: int
    file_content_max_tokens_per_file: int = 5000
    file_content_max_total_tokens: int = 15000


@lru_cache(maxsize=1)
def get_llm_config() -> LLMConfig:
    path = Path(__file__).parent / "llm_config.yaml"
    data = yaml.safe_load(path.read_text())
    return LLMConfig(
        model_chain=data["model_chain"],
        reasoning_model=data["reasoning_model"],
        no_training_header=data["no_training_header"],
        no_retention_header=data["no_retention_header"],
        snippet_pool_size=data["snippet_pool_size"],
        snippet_diff_threshold=data["snippet_diff_threshold"],
        snippet_whitespace_filter=data["snippet_whitespace_filter"],
        snippet_token_budget=data["snippet_token_budget"],
        snippet_max_count=data["snippet_max_count"],
        validation_retry_count=data["validation_retry_count"],
        file_content_max_tokens_per_file=data.get("file_content_max_tokens_per_file", 5000),
        file_content_max_total_tokens=data.get("file_content_max_total_tokens", 15000),
    )
