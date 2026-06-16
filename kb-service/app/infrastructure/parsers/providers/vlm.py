"""LiteLLM-routed VLM OCR provider for scanned PDFs."""
from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import Callable
from dataclasses import dataclass

import structlog

from app.core.config import settings
from app.infrastructure.parsers.contracts.errors import (
    CorruptFileError,
    OCRTimeoutError,
    UnsupportedFileTypeError,
)
from app.infrastructure.parsers.contracts.models import ParseArtifacts, ParseOutcome

logger = structlog.get_logger(__name__)

VLM_OCR_NO_TEXT_SENTINEL = "__NO_TEXT_EXTRACTED__"
_VLM_OCR_ROUTE = "vlm_ocr"
_VLM_OCR_PARSER_ID = "vlm_ocr_pdf"
_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


@dataclass(slots=True)
class VLMOCRProvider:
    """OCR scanned/image-dominant PDFs through a LiteLLM vision model alias."""

    client_factory: Callable[[], object] | None = None
    provider: str = "vlm"

    async def parse_pdf_high_complexity(
        self,
        *,
        path: str,
        filename: str,
        s3_bucket: str | None,
        s3_key: str | None,
    ) -> ParseOutcome | None:
        return await asyncio.to_thread(
            self._parse_pdf_high_complexity_sync,
            path=path,
            filename=filename,
        )

    async def parse_image_s3(self, *, s3_bucket: str | None, s3_key: str | None) -> ParseOutcome:
        raise UnsupportedFileTypeError(
            "Standalone image OCR is not part of the shared KB parser route; upload a supported document type."
        )

    def _parse_pdf_high_complexity_sync(
        self,
        *,
        path: str,
        filename: str,
    ) -> ParseOutcome | None:
        started_at = time.perf_counter()
        page_images = _render_pdf_pages(
            path=path,
            dpi=settings.VLM_OCR_DPI,
            max_pages=settings.VLM_OCR_MAX_PAGES,
        )
        client = self._build_client()
        text_segments: list[str] = []
        text_segment_locators: list[dict[str, int | str]] = []

        for page in page_images.pages:
            page_text = self._extract_page_text(
                client=client,
                filename=filename,
                page_number=page.page_number,
                png_bytes=page.png_bytes,
            )
            if page_text:
                text_segments.append(page_text)
                text_segment_locators.append(
                    {
                        "type": "page",
                        "page_index": page.page_number - 1,
                        "page_number": page.page_number,
                    }
                )

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "vlm_ocr_pdf_completed",
            filename=filename,
            provider=self.provider,
            model=settings.LITELLM_VLM_MODEL,
            page_count=page_images.total_page_count,
            rendered_page_count=len(page_images.pages),
            extracted_page_count=len(text_segments),
            elapsed_ms=elapsed_ms,
        )

        if not text_segments:
            return None

        return ParseOutcome(
            text_segments=text_segments,
            artifacts=ParseArtifacts(),
            selected_parser=_VLM_OCR_PARSER_ID,
            route=_VLM_OCR_ROUTE,
            text_segment_locators=text_segment_locators,
            reason_codes=["vlm_ocr_selected"],
            quality_signals={
                "provider": self.provider,
                "model": settings.LITELLM_VLM_MODEL,
                "page_count": page_images.total_page_count,
                "rendered_page_count": len(page_images.pages),
                "extracted_page_count": len(text_segments),
                "dpi": settings.VLM_OCR_DPI,
                "detail": settings.VLM_OCR_DETAIL,
                "truncated": page_images.total_page_count > len(page_images.pages),
            },
        )

    def _build_client(self) -> object:
        if self.client_factory is not None:
            return self.client_factory()
        from openai import OpenAI

        return OpenAI(
            base_url=settings.LITELLM_BASE_URL,
            api_key=settings.LITELLM_API_KEY,
            timeout=settings.VLM_OCR_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )

    def _extract_page_text(
        self,
        *,
        client: object,
        filename: str,
        page_number: int,
        png_bytes: bytes,
    ) -> str:
        request_started_at = time.perf_counter()
        try:
            response = (
                client.chat.completions.create(  # type: ignore[attr-defined]
                    model=settings.LITELLM_VLM_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": _build_page_prompt(
                                        filename=filename,
                                        page_number=page_number,
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": _to_png_data_url(png_bytes),
                                        "detail": settings.VLM_OCR_DETAIL,
                                    },
                                },
                            ],
                        }
                    ],
                    temperature=0,
                )
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - request_started_at) * 1000)
            _raise_sanitized_vlm_error(
                exc,
                filename=filename,
                page_number=page_number,
                elapsed_ms=elapsed_ms,
            )

        return _normalize_page_text(_response_text(response))


@dataclass(frozen=True, slots=True)
class _RenderedPage:
    page_number: int
    png_bytes: bytes


@dataclass(frozen=True, slots=True)
class _RenderedPdf:
    total_page_count: int
    pages: list[_RenderedPage]


def _render_pdf_pages(*, path: str, dpi: int, max_pages: int) -> _RenderedPdf:
    import fitz

    try:
        with fitz.open(filename=path) as document:
            total_page_count = len(document)
            pages: list[_RenderedPage] = []
            for index, page in enumerate(document):
                if index >= max_pages:
                    break
                pixmap = page.get_pixmap(dpi=dpi)
                pages.append(
                    _RenderedPage(
                        page_number=index + 1,
                        png_bytes=bytes(pixmap.tobytes("png")),
                    )
                )
            return _RenderedPdf(total_page_count=total_page_count, pages=pages)
    except Exception as exc:
        logger.exception("vlm_ocr_pdf_render_failed", error=str(exc))
        raise CorruptFileError("Failed to render PDF pages for VLM OCR") from exc


def _build_page_prompt(*, filename: str, page_number: int) -> str:
    return (
        "Transcribe all legible text from this scanned PDF page in natural reading order. "
        "Return only the transcribed text. Do not summarize, explain, infer missing words, "
        "or add formatting that is not visible. "
        f"If no legible text is present, return exactly {VLM_OCR_NO_TEXT_SENTINEL}. "
        f"File: {filename}. Page: {page_number}."
    )


def _to_png_data_url(png_bytes: bytes) -> str:
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _response_text(response: object) -> str:
    choices = getattr(response, "choices", [])
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "\n".join(parts)
    return ""


def _normalize_page_text(text: str) -> str:
    normalized = text.strip()
    if normalized.upper() == VLM_OCR_NO_TEXT_SENTINEL:
        return ""
    return normalized


def _raise_sanitized_vlm_error(
    exc: Exception,
    *,
    filename: str,
    page_number: int,
    elapsed_ms: int,
) -> None:
    status_code = _status_code(exc)
    retryable = _is_retryable_vlm_error(exc, status_code=status_code)
    logger.warning(
        "vlm_ocr_page_failed",
        filename=filename,
        page_number=page_number,
        status_code=status_code,
        retryable=retryable,
        elapsed_ms=elapsed_ms,
        exception_class=type(exc).__name__,
    )
    if retryable:
        raise OCRTimeoutError("VLM OCR upstream request failed with a retryable error") from exc
    raise CorruptFileError("VLM OCR upstream request failed") from exc


def _is_retryable_vlm_error(exc: Exception, *, status_code: int | None) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if status_code in _RETRYABLE_STATUS_CODES:
        return True
    try:
        from openai import APIConnectionError, APITimeoutError, RateLimitError
    except Exception:
        return False
    return isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError))


def _status_code(exc: Exception) -> int | None:
    direct_status = getattr(exc, "status_code", None)
    if isinstance(direct_status, int):
        return direct_status
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None
