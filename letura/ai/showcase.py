"""Pre-generated AI answers for the showcase edition.

`scripts/generate_showcase_answers.py` runs every suggested question once with the live
analyst and stores the answers (text + the tool results that grounded them) in
data/snapshot/ai_showcase.json. When no live AI is available (e.g. the public cloud demo),
`Analyst.answer` serves these stored answers for the exact suggested questions, so viewers
see real AI output without spending API credits.
"""
from __future__ import annotations

import json
from functools import lru_cache

from letura.config import PROJECT_ROOT

SHOWCASE_PATH = PROJECT_ROOT / "data" / "snapshot" / "ai_showcase.json"


def normalise(question: str) -> str:
    return " ".join(str(question).lower().split()).rstrip("?.! ")


@lru_cache(maxsize=1)
def load() -> dict:
    try:
        raw = json.loads(SHOWCASE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {normalise(k): v for k, v in raw.get("answers", {}).items()}


def lookup(question: str) -> dict | None:
    return load().get(normalise(question))


def available() -> int:
    return len(load())
