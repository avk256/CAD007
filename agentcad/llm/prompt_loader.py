from __future__ import annotations

from pathlib import Path


_PROMPT_DIR = Path(__file__).with_name("prompts")


def load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
