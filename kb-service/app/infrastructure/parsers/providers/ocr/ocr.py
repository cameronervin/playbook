"""OCR provider abstraction and factory for parser routing (SCAFFOLD STUB).

This is the key genericization point. In the source service two concrete OCR
providers backed the "high complexity" PDF route and image parsing:

  * a Textract provider (AWS Textract async document analysis + result polling)
  * a VLM provider (OpenAI Vision: rasterise pages and caption them)

Both were dropped from the scaffold to keep it dependency-light and
vendor-neutral. What remains is:

  * ``BaseOCRProvider`` — the Protocol every real provider must satisfy.
  * ``NullOCRProvider`` — the default. ``parse_pdf_high_complexity`` returns
    ``None``, which the PDF router reads as "no OCR available — fall back to
    the native text extractor". ``parse_image_s3`` raises, because there is no
    sensible text-only fallback for an image.
  * ``build_ocr_provider`` — factory keyed off ``settings.OCR_PROVIDER``.

To plug a real provider back in, implement ``BaseOCRProvider``, return it from
``build_ocr_provider`` for the matching ``OCR_PROVIDER`` value, and set
``OCR_PROVIDER=textract`` or ``vlm``. See ``app/infrastructure/STUBS.md``.
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

        Returning ``None`` signals "no OCR available" — the PDF router then
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
            "OCR provider not configured; image parsing requires Textract or VLM — see STUBS.md"
        )


def build_ocr_provider(provider: OCRProvider | None = None) -> BaseOCRProvider:
    """Return the configured OCR provider.

    Defaults to ``settings.OCR_PROVIDER`` (``"none"`` in the scaffold). The
    ``textract``/``vlm`` branches are intentionally unimplemented stubs — wire
    in a real ``BaseOCRProvider`` here when you implement them.
    """
    selected_provider = provider or settings.OCR_PROVIDER
    if selected_provider == "none":
        return NullOCRProvider()
    if selected_provider in ("textract", "vlm"):
        raise NotImplementedError(
            "Textract/VLM OCR not implemented in scaffold — see app/infrastructure/STUBS.md"
        )
    raise UnsupportedFileTypeError(f"Unsupported OCR provider: {selected_provider}")
