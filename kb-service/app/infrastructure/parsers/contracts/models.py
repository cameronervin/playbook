"""Parser result models used by router + worker telemetry.

These are frozen dataclasses (immutable value objects). A parser produces a
``ParseOutcome``; the router enriches its ``reason_codes`` / ``quality_signals``
by constructing a *new* outcome (never mutating) so the audit trail of how a
document was routed is preserved end to end.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParseArtifacts:
    """Structured artifacts extracted alongside normalized text."""

    tables: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    layout_blocks: list[dict[str, Any]] = field(default_factory=list)
    source_refs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tables": list(self.tables),
            "figures": list(self.figures),
            "layout_blocks": list(self.layout_blocks),
            "source_refs": list(self.source_refs),
        }

    def summary(self) -> dict[str, int]:
        return {
            "tables": len(self.tables),
            "figures": len(self.figures),
            "layout_blocks": len(self.layout_blocks),
            "source_refs": len(self.source_refs),
        }


@dataclass(frozen=True)
class ParseOutcome:
    """Final parse output and route metadata."""

    text_segments: list[str]
    artifacts: ParseArtifacts
    selected_parser: str
    route: str
    text_segment_locators: list[dict[str, Any]] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    quality_signals: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def pages(self) -> list[str]:
        """Backward-compatible alias used by existing pipeline stages."""
        return self.text_segments

    @property
    def text_segment_records(self) -> list[dict[str, Any]]:
        """Return streamable text records with optional source locators."""
        records: list[dict[str, Any]] = []
        for index, text in enumerate(self.text_segments):
            record: dict[str, Any] = {"text": text}
            if index < len(self.text_segment_locators):
                locator = self.text_segment_locators[index]
                if locator:
                    record["source_locator"] = dict(locator)
            records.append(record)
        return records

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_parser": self.selected_parser,
            "route": self.route,
            "reason_codes": list(self.reason_codes),
            "quality_signals": dict(self.quality_signals),
            "warnings": list(self.warnings),
            "artifacts": self.artifacts.to_dict(),
            "artifact_summary": self.artifacts.summary(),
            "text_segment_count": len(self.text_segments),
        }
