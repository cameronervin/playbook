"""Native DOCX parser (python-docx).

The "low complexity" DOCX path: a fast, dependency-light text extractor that
joins all non-empty paragraphs. ``from docx import Document`` is imported lazily
inside the method so this module compiles without python-docx installed.
"""
from __future__ import annotations

from typing import IO

import structlog

from app.infrastructure.parsers.contracts.base import build_text_only_outcome
from app.infrastructure.parsers.contracts.errors import CorruptFileError
from app.infrastructure.parsers.contracts.models import ParseOutcome

logger = structlog.get_logger(__name__)


class NativeDOCXParser:
    parser_id = "native_docx"

    def parse(self, file: IO[bytes], filename: str) -> list[str]:
        from docx import Document

        try:
            file.seek(0)
            document = Document(file)
            paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
            if not paragraphs:
                return []
            return ["\n".join(paragraphs)]
        except Exception as exc:  # pragma: no cover - dependency-specific failures
            logger.exception("docx_parse_failed", filename=filename, error=str(exc))
            raise CorruptFileError(f"Failed to parse DOCX: {filename}") from exc

    def parse_path(self, path: str, filename: str) -> list[str]:
        with open(path, "rb") as file:
            return self.parse(file, filename)

    def parse_outcome_path(self, path: str, filename: str) -> ParseOutcome:
        return build_text_only_outcome(
            text_segments=self.parse_path(path, filename),
            selected_parser=self.parser_id,
            route="extractor",
        )
