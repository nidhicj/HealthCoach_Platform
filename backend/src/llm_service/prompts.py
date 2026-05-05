"""Prompt file loader: YAML frontmatter + body. Per ADR-0003 §2."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass(frozen=True)
class PromptFile:
    version: str
    body: str


def load_prompt(name: str) -> PromptFile:
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {name}.md (looked in {_PROMPTS_DIR})")
    text = path.read_text()
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"Prompt {name}.md is missing YAML frontmatter (expected --- block)")
    frontmatter = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return PromptFile(version=str(frontmatter["version"]), body=body)
