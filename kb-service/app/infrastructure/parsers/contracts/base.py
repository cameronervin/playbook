"""Parser contracts and ParseOutcome helpers."""
from __future__ import annotations

from typing import IO, Any, Protocol, runtime_checkable

from app.infrastructure.parsers.contracts.models import ParseArtifacts, ParseOutcome


@runtime_checkable
class ITextParser(Protocol):
    """Compatibility contract for native text-only extractors."""

    def parse(self, file: IO[bytes], filename: str) -> list[str]:
        """Parse a file-like object and return page/section text strings."""
        ...

    def parse_path(self, path: str, filename: str) -> list[str]:
        """Parse from a filesystem path."""
        with open(path, "rb") as file:
            return self.parse(file, filename)


@runtime_checkable
class IOutcomeParser(Protocol):
    """Routing-facing parser contract."""

    def parse_outcome_path(self, path: str, filename: str) -> ParseOutcome:
        ...


@runtime_checkable
class IStructuredParser(Protocol):
    """Structured parser contract used by Docling-style extractors."""

    def parse_structured_path(self, path: str, filename: str) -> ParseOutcome:
        ...


def build_text_only_outcome(
    *,
    text_segments: list[str],
    selected_parser: str,
    route: str,
    reason_codes: list[str] | None = None,
    quality_signals: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> ParseOutcome:
    """Wrap plain text segments in a ParseOutcome with empty artifacts."""
    return ParseOutcome(
        text_segments=text_segments,
        artifacts=ParseArtifacts(),
        selected_parser=selected_parser,
        route=route,
        reason_codes=reason_codes or [],
        quality_signals=quality_signals or {},
        warnings=warnings or [],
    )

