"""Parser contracts and MIME dispatch primitives.

This module defines the two parser Protocols every extractor satisfies plus the
global ``PARSER_DISPATCH`` registry. Adding a new file type is a two-step move:

  1. Implement a class with ``parse(file, filename) -> list[str]`` (and you get
     ``parse_path`` for free, or override it for path-based libraries).
  2. Register it at module scope: ``PARSER_DISPATCH[<mime>] = MyParser``.

The Protocols are ``runtime_checkable`` so the router can ``isinstance``-check
a parser against ``IStructuredParser`` to decide whether structured artifacts
are available, without importing concrete parser classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import IO, Any, Protocol, runtime_checkable

from app.infrastructure.parsers.contracts.models import ParseArtifacts, ParseOutcome


@runtime_checkable
class IParser(Protocol):
    def parse(self, file: IO[bytes], filename: str) -> list[str]:
        """Parse a file-like object and return a list of page/section text strings."""
        ...

    def parse_path(self, path: str, filename: str) -> list[str]:
        """Parse from a filesystem path (preferred for mmap/path-based libraries)."""
        with open(path, "rb") as file:
            return self.parse(file, filename)


@runtime_checkable
class IStructuredParser(Protocol):
    """Parser that returns normalized text plus structured artifacts."""

    def parse_structured(self, file: IO[bytes], filename: str) -> ParseOutcome:
        ...

    def parse_structured_path(self, path: str, filename: str) -> ParseOutcome:
        with open(path, "rb") as file:
            return self.parse_structured(file, filename)


@dataclass(frozen=True)
class ParseRouteDecision:
    """Structured route/quality metadata for parser observability."""

    selected_parser: str
    route: str
    reason_codes: list[str] = field(default_factory=list)
    quality_signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_parser": self.selected_parser,
            "route": self.route,
            "reason_codes": list(self.reason_codes),
            "quality_signals": dict(self.quality_signals),
        }


def build_text_only_outcome(
    *,
    text_segments: list[str],
    selected_parser: str,
    route: str,
    reason_codes: list[str] | None = None,
    quality_signals: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> ParseOutcome:
    """Wrap plain text segments in a ``ParseOutcome`` with empty artifacts.

    Convenience used by every "text only" parser path (native extractors and
    OCR fallbacks) so they don't each have to construct an empty
    ``ParseArtifacts``.
    """
    return ParseOutcome(
        text_segments=text_segments,
        artifacts=ParseArtifacts(),
        selected_parser=selected_parser,
        route=route,
        reason_codes=reason_codes or [],
        quality_signals=quality_signals or {},
        warnings=warnings or [],
    )


# MIME-type -> parser class dispatch table (populated by each parser module
# at import time via ``PARSER_DISPATCH[<mime>] = ParserClass``). Call
# ``load_parser_registry()`` (parsers/__init__.py) once to force all extractor
# modules to import and register themselves.
PARSER_DISPATCH: dict[str, type[IParser]] = {}
