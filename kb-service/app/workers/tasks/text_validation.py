"""Text-presence guards shared by KB ingestion worker tasks."""
from __future__ import annotations


def _has_usable_text_segments(text_segments) -> bool:
    """Return true when parser output contains text worth chunking."""
    return any(isinstance(segment, str) and segment.strip() for segment in text_segments)


def _ensure_parse_outcome_has_usable_text(outcome, *, filename: str) -> None:
    from app.infrastructure.parsers.contracts.errors import NoTextExtractedError

    if not _has_usable_text_segments(getattr(outcome, "text_segments", [])):
        raise NoTextExtractedError(stage="parse", filename=filename)
