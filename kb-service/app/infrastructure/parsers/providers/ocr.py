"""OCR provider abstraction and factory for parser routing.

This is the key genericization point. The product path supports:

  * ``NullOCRProvider`` — the default. ``parse_pdf_high_complexity`` returns
    ``None``, which ``ParserRouter`` reads as "no OCR available — fall back to
    the native text extractor". ``parse_image_s3`` raises, because there is no
    image route in the shared KB MVP.
  * ``VLMOCRProvider`` — opt-in via ``OCR_PROVIDER="vlm"``. It rasterises
    scanned PDF pages and transcribes them through a LiteLLM vision model alias.

Textract is intentionally unsupported for Playbook; OCR must route through
LiteLLM credentials/model aliases.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.core.config import settings
from app.infrastructure.parsers.contracts.errors import UnsupportedFileTypeError
from app.infrastructure.parsers.contracts.models import ParseOutcome

OCRProvider = Literal["none", "textract", "vlm"]


class BaseOCRProvider(Protocol):
    """Contract for an OCR backend used by the high-complexity parser routes."""

    provider: OCRProvider

    async def parse_pdf_high_complexity(
        self,
        *,
        path: str,
        filename: str,
        s3_bucket: str | None,
        s3_key: str | None,
    ) -> ParseOutcome | None:
        """Parse a scanned / image-dominant PDF via OCR.

        Returning ``None`` signals "no OCR available" — ``ParserRouter`` then
        falls back to the native text extractor.
        """
        ...

    async def parse_image_s3(self, *, s3_bucket: str | None, s3_key: str | None) -> ParseOutcome:
        """OCR an image object stored in S3 and return extracted text."""
        ...


@dataclass
class NullOCRProvider:
    """Default no-op OCR provider used when ``OCR_PROVIDER="none"``.

    High-complexity PDFs degrade gracefully to native text extraction (the
    router treats a ``None`` return as "fall back to NativePDFParser"). Images
    have no text-only fallback, so requesting image OCR raises an explicit,
    actionable error.
    """

    provider: OCRProvider = "none"

    async def parse_pdf_high_complexity(
        self,
        *,
        path: str,
        filename: str,
        s3_bucket: str | None,
        s3_key: str | None,
    ) -> ParseOutcome | None:
        # No OCR configured → tell the router to fall back to native text.
        return None

    async def parse_image_s3(self, *, s3_bucket: str | None, s3_key: str | None) -> ParseOutcome:
        raise UnsupportedFileTypeError(
            "OCR provider not configured; image parsing is not part of the shared KB parser route"
        )


def build_ocr_provider(provider: OCRProvider | None = None) -> BaseOCRProvider:
    """Return the configured OCR provider.

    Defaults to ``settings.OCR_PROVIDER``. ``textract`` intentionally remains
    unsupported for Playbook; use ``vlm`` to route OCR through LiteLLM.
    """
    selected_provider = provider or settings.OCR_PROVIDER
    if selected_provider == "none":
        return NullOCRProvider()
    if selected_provider == "vlm":
        from app.infrastructure.parsers.providers.vlm import VLMOCRProvider

        return VLMOCRProvider()
    if selected_provider == "textract":
        raise NotImplementedError(
            "Textract OCR is not supported for Playbook; set OCR_PROVIDER=vlm to use LiteLLM-routed vision OCR"
        )
    raise UnsupportedFileTypeError(f"Unsupported OCR provider: {selected_provider}")
