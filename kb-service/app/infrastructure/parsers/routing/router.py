"""Top-level parser router: MIME dispatch + route metadata.

Resolves a MIME type, then dispatches:

    application/pdf            -> PDFRouter (complexity-based)
    DOCX / PPTX                -> OfficeRouter when docling routing is enabled,
                                  else the native parser directly
    everything else (xlsx, …)  -> the native parser registered in PARSER_DISPATCH

The image (``image/``) branch from the source service has been DROPPED — image
OCR depended on the now-stubbed OCR providers. The OCR provider is still built
and threaded into the PDF router so a real provider can handle scanned PDFs.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

import structlog

from app.core.config import settings
from app.infrastructure.parsers import load_parser_registry
from app.infrastructure.parsers.contracts.base import IParser, PARSER_DISPATCH, build_text_only_outcome
from app.infrastructure.parsers.contracts.errors import UnsupportedFileTypeError
from app.infrastructure.parsers.contracts.models import ParseOutcome
from app.infrastructure.parsers.providers.ocr.ocr import BaseOCRProvider, build_ocr_provider
from app.infrastructure.parsers.routing.complexity import DOCX_MIME, PDF_MIME, PPTX_MIME
from app.infrastructure.parsers.routing.office import OfficeRouter
from app.infrastructure.parsers.routing.pdf import PDFRouter

logger = structlog.get_logger(__name__)


def _guess_mime(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    known_mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(suffix)
    if known_mime:
        return known_mime
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


class ParserRouter:
    """Primary parser router used by parse_task."""

    def __init__(
        self,
        pdf_router: PDFRouter | None = None,
        ocr_provider: BaseOCRProvider | None = None,
    ) -> None:
        load_parser_registry()
        self._office_router = OfficeRouter()
        provider = ocr_provider or build_ocr_provider()
        self._pdf_router = pdf_router or PDFRouter(ocr_provider=provider)

    def _build_parser(self, mime_type: str) -> IParser:
        parser_cls = PARSER_DISPATCH.get(mime_type)
        if parser_cls is None:
            raise UnsupportedFileTypeError(f"Unsupported MIME type: {mime_type}")
        return parser_cls()

    async def route_path(
        self,
        *,
        path: str,
        filename: str,
        mime_type: str | None = None,
        s3_bucket: str | None = None,
        s3_key: str | None = None,
    ) -> ParseOutcome:
        resolved_mime = mime_type or _guess_mime(filename)

        if resolved_mime == PDF_MIME:
            return await self._pdf_router.route_path(
                path=path,
                filename=filename,
                s3_bucket=s3_bucket,
                s3_key=s3_key,
            )

        parser = self._build_parser(resolved_mime)

        if resolved_mime in {DOCX_MIME, PPTX_MIME} and settings.ENABLE_DOCLING_ROUTING:
            return self._office_router.route_path(
                parser=parser,
                path=path,
                filename=filename,
                mime_type=resolved_mime,
            )

        return self._parse_with_local_parser(parser=parser, path=path, filename=filename)

    @staticmethod
    def _parse_with_local_parser(*, parser: IParser, path: str, filename: str) -> ParseOutcome:
        return build_text_only_outcome(
            text_segments=parser.parse_path(path, filename),
            selected_parser=parser.__class__.__name__,
            route="direct_path",
            reason_codes=["path_parse"],
        )
