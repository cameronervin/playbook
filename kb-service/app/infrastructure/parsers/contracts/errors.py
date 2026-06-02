"""Parser-layer exception hierarchy."""
from __future__ import annotations


class ParserError(Exception):
    """Base parser error."""


class UnsupportedFileTypeError(ParserError):
    """Raised when no parser is registered for a MIME type."""


class CorruptFileError(ParserError):
    """Raised when source file cannot be parsed due to corruption."""


class OCRTimeoutError(ParserError):
    """Raised when OCR provider does not finish within timeout."""


class ParseWarning(ParserError):
    """Raised for soft parse-quality issues (e.g., likely scanned PDF)."""
