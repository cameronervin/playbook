"""Native DOCX parser (python-docx).

The "low complexity" DOCX path: a fast, dependency-light text extractor that
joins all non-empty paragraphs. ``from docx import Document`` is imported lazily
inside the method so this module compiles without python-docx installed.
"""
from __future__ import annotations

from typing import IO

import structlog

from app.infrastructure.parsers.contracts.base import PARSER_DISPATCH
from app.infrastructure.parsers.contracts.errors import CorruptFileError

logger = structlog.get_logger(__name__)


class NativeDOCXParser:
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
            logger.error("docx_parse_failed", filename=filename, error=str(exc))
            raise CorruptFileError(f"Failed to parse DOCX: {filename}") from exc

    def parse_path(self, path: str, filename: str) -> list[str]:
        with open(path, "rb") as file:
            return self.parse(file, filename)


PARSER_DISPATCH[
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
] = NativeDOCXParser
