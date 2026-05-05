"""Unit tests for llm_service config loading. Per ADR-0003 §1."""
import pytest

from src.llm_service.config import LLMConfig, get_llm_config


def test_get_llm_config_returns_llm_config():
    cfg = get_llm_config()
    assert isinstance(cfg, LLMConfig)


def test_model_chain_is_list_of_strings():
    cfg = get_llm_config()
    assert isinstance(cfg.model_chain, list)
    assert len(cfg.model_chain) >= 1
    assert all(isinstance(m, str) for m in cfg.model_chain)


def test_model_chain_head_is_llama():
    cfg = get_llm_config()
    assert "llama" in cfg.model_chain[0]


def test_snippet_pool_size_is_positive_int():
    cfg = get_llm_config()
    assert isinstance(cfg.snippet_pool_size, int)
    assert cfg.snippet_pool_size > 0


def test_snippet_token_budget_is_positive_int():
    cfg = get_llm_config()
    assert isinstance(cfg.snippet_token_budget, int)
    assert cfg.snippet_token_budget > 0


def test_validation_retry_count_is_one():
    cfg = get_llm_config()
    assert cfg.validation_retry_count == 1


def test_get_llm_config_is_cached():
    cfg1 = get_llm_config()
    cfg2 = get_llm_config()
    assert cfg1 is cfg2
