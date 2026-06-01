"""Small pure text helpers used by serializers and nodes.

Pattern: agent-layer utilities are pure functions (no I/O, no LLM calls) that
serializers, prompts, and nodes can share. Keep side-effectful logic in nodes.
"""

from __future__ import annotations


def truncate_text(text: str, max_chars: int = 200, suffix: str = "...") -> str:
    """Truncate ``text`` to ``max_chars``, appending ``suffix`` when trimmed."""
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    cut = max(0, max_chars - len(suffix))
    return text[:cut] + suffix
