"""Extended scrub tests for P4 PII keys (prompt_text, completion_text)."""
from src.telemetry.scrub import scrub


def test_prompt_text_key_is_redacted():
    result = scrub({"prompt_text": "You are a health coach. Client CP0001 had issue..."})
    assert result["prompt_text"] == "<redacted>"


def test_completion_text_key_is_redacted():
    result = scrub({"completion_text": '{"summary": "Client improved sleep..."}'})
    assert result["completion_text"] == "<redacted>"


def test_nested_prompt_text_is_redacted():
    result = scrub({"llm": {"prompt_text": "some prompt", "model": "llama"}})
    assert result["llm"]["prompt_text"] == "<redacted>"
    assert result["llm"]["model"] == "llama"


def test_non_pii_fields_pass_through():
    result = scrub({"model_requested": "meta-llama/llama-3.3-70b-instruct:free", "latency_ms": 450})
    assert result["model_requested"] == "meta-llama/llama-3.3-70b-instruct:free"
    assert result["latency_ms"] == 450
