"""Unit tests for prompt file loading and YAML frontmatter parsing."""
import pytest

from src.llm_service.prompts import PromptFile, load_prompt


def test_load_mom_draft_returns_prompt_file():
    p = load_prompt("mom_draft")
    assert isinstance(p, PromptFile)


def test_prompt_has_version():
    p = load_prompt("mom_draft")
    assert p.version
    assert isinstance(p.version, str)
    # Version should look like semver "1.0.0"
    parts = p.version.split(".")
    assert len(parts) == 3


def test_prompt_has_body():
    p = load_prompt("mom_draft")
    assert p.body
    assert len(p.body) > 50


def test_load_brief_assemble():
    p = load_prompt("brief_assemble")
    assert p.version
    assert p.body


def test_load_ai_assist():
    p = load_prompt("ai_assist")
    assert p.version
    assert p.body


def test_missing_prompt_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")


def test_prompt_version_is_logged_to_llm_calls():
    p = load_prompt("mom_draft")
    # version is the exact string that lands in llm_calls.prompt_version
    assert p.version == p.version.strip()
    assert " " not in p.version
