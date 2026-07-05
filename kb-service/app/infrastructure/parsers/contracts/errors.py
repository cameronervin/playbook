"""Parser-layer exception hierarchy."""
from __future__ import annotations


class ParserError(Exception):
    """Base parser error."""


class UnsupportedFileTypeError(ParserError):
    """Raised when no parser is registered for a MIME type."""


class CorruptFileError(ParserError):
    """Raised when source file cannot be parsed due to corruption."""


NO_TEXT_ERROR_CODE = "NO_TEXT_EXTRACTED"


class NoTextExtractedError(ParserError):
    """Raised when a document yields no usable text for KB retrieval."""

    def __init__(
        self,
        *,
        stage: str,
        filename: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.code = NO_TEXT_ERROR_CODE
        self.stage = stage
        self.filename = filename
        self.detail = detail
        message = (
            f"{NO_TEXT_ERROR_CODE}: No usable text could be extracted during "
            f"the {stage} stage. Re-upload a text-based document or enable OCR "
            "for scanned/image-only files."
        )
        if detail:
            message = f"{message} Detail: {detail}"
        super().__init__(message)


class OCRTimeoutError(ParserError):
    """Raised when OCR provider does not finish within timeout."""


class ParseWarning(ParserError):
    """Raised for soft parse-quality issues (e.g., likely scanned PDF)."""
