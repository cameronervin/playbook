"""Conversation title helpers."""

from __future__ import annotations

import re

PROVISIONAL_TITLE_WORD_LIMIT = 8
PROVISIONAL_TITLE_CHAR_LIMIT = 80
AI_TITLE_WORD_LIMIT = 7
AI_TITLE_CHAR_LIMIT = 60

_TRAILING_TITLE_PUNCTUATION = " .?!,:;-"


def create_provisional_conversation_title(content: str) -> str:
    """Create an immediate, deterministic title from the first user message."""
    words = _words(content)
    title = " ".join(words[:PROVISIONAL_TITLE_WORD_LIMIT])
    return _clean_title(title, max_chars=PROVISIONAL_TITLE_CHAR_LIMIT) or "New chat"


def normalize_ai_conversation_title(
    title: str,
    *,
    fallback: str,
) -> str:
    """Normalize a model-generated title while preserving a safe fallback."""
    words = _words(title)
    normalized = _clean_title(
        " ".join(words[:AI_TITLE_WORD_LIMIT]),
        max_chars=AI_TITLE_CHAR_LIMIT,
    )
    return normalized or fallback


def _words(value: str) -> list[str]:
    return re.sub(r"\s+", " ", value.strip()).split()


def _clean_title(value: str, *, max_chars: int) -> str:
    title = value.strip().strip("\"'")
    if len(title) > max_chars:
        title = title[:max_chars].rsplit(" ", maxsplit=1)[0] or title[:max_chars]
    return title.strip().strip("\"'").rstrip(_TRAILING_TITLE_PUNCTUATION)
