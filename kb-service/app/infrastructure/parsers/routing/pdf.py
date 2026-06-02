"""PDF complexity router.

Routes a PDF to one of three parsers based on the deterministic complexity
decision:

    high   -> OCR provider (``parse_pdf_high_complexity``). The scaffold ships
              the NullOCRProvider, which returns ``None`` here — so we fall back
              to the native text extractor with an ``ocr_unavailable_fallback_native``
              reason code. Wire a real OCR provider in to handle scanned PDFs.
    medium -> Docling (structured extraction), with native fallback on failure.
    low    -> native PyMuPDF text extractor.

The source service used the ``unstructured`` library for the local path; the
scaffold replaces it with ``NativePDFParser`` (PyMuPDF). Docling is imported
lazily (constructed on demand) so this module compiles without it installed.
"""
from __future__ import annotations

import structlog

from app.core.config import settings
from app.infrastructure.parsers.contracts.base import IParser, build_text_only_outcome
from app.infrastructure.parsers.contracts.errors import CorruptFileError
from app.infrastructure.parsers.contracts.models import ParseOutcome
from app.infrastructure.parsers.extractors.docling import DoclingPDFParser
from app.infrastructure.parsers.extractors.pdf_native import NativePDFParser
from app.infrastructure.parsers.providers.ocr.ocr import BaseOCRProvider, build_ocr_provider
from app.infrastructure.parsers.routing.complexity import ComplexityAssessor, ComplexityDecision

logger = structlog.get_logger(__name__)


class PDFRouter:
    """Route PDFs to native parser, Docling, or OCR fallback."""

    def __init__(
        self,
        local_parser: IParser | None = None,
        docling_parser: DoclingPDFParser | None = None,
        complexity_assessor: ComplexityAssessor | None = None,
        ocr_provider: BaseOCRProvider | None = None,
    ) -> None:
        self._local = local_parser or NativePDFParser()
        self._docling = docling_parser
        self._assessor = complexity_assessor or ComplexityAssessor()
        self._ocr_provider = ocr_provider or build_ocr_provider()

    async def route_path(
        self,
        *,
        path: str,
        filename: str,
        s3_bucket: str | None = None,
        s3_key: str | None = None,
    ) -> ParseOutcome:
        decision = self._assessor.assess(
            path=path,
            filename=filename,
            mime_type="application/pdf",
        )
        return await self._route_by_complexity(
            decision=decision,
            path=path,
            filename=filename,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
        )

    async def _route_by_complexity(
        self,
        *,
        decision: ComplexityDecision,
        path: str,
        filename: str,
        s3_bucket: str | None,
        s3_key: str | None,
    ) -> ParseOutcome:
        if decision.category == "high":
            outcome = await self._ocr_provider.parse_pdf_high_complexity(
                path=path,
                filename=filename,
                s3_bucket=s3_bucket,
                s3_key=s3_key,
            )
            if outcome:
                return ParseOutcome(
                    text_segments=outcome.text_segments,
                    artifacts=outcome.artifacts,
                    selected_parser=outcome.selected_parser,
                    route="pdf_router",
                    reason_codes=list(decision.reason_codes) + [f"ocr_fallback_{self._ocr_provider.provider}"],
                    quality_signals=decision.quality_signals,
                    warnings=outcome.warnings,
                )
            # OCR provider returned None (e.g. NullOCRProvider when OCR_PROVIDER
            # is "none", or missing S3 identity). Degrade gracefully to native
            # text extraction so ingestion does not hard-fail on a scanned PDF.
            local_text = self._local.parse_path(path, filename)
            local_outcome = build_text_only_outcome(
                text_segments=local_text,
                selected_parser=self._local.__class__.__name__,
                route="pdf_native_local",
                reason_codes=["pdf_native_local"],
            )
            return ParseOutcome(
                text_segments=local_outcome.text_segments,
                artifacts=local_outcome.artifacts,
                selected_parser=local_outcome.selected_parser,
                route="pdf_router",
                reason_codes=list(decision.reason_codes) + ["ocr_unavailable_fallback_native"],
                quality_signals=decision.quality_signals,
                warnings=local_outcome.warnings + ["ocr_unavailable_fallback_native"],
            )

        if decision.category == "medium" and settings.DOCLING_ENABLED and settings.ENABLE_DOCLING_ROUTING:
            try:
                docling_parser = self._docling or DoclingPDFParser()
                docling_outcome = docling_parser.parse_structured_path(path, filename)
                return ParseOutcome(
                    text_segments=docling_outcome.text_segments,
                    artifacts=docling_outcome.artifacts,
                    selected_parser=docling_outcome.selected_parser,
                    route="pdf_router",
                    reason_codes=list(decision.reason_codes) + ["docling_primary"],
                    quality_signals=decision.quality_signals | docling_outcome.quality_signals,
                    warnings=docling_outcome.warnings,
                )
            except CorruptFileError:
                logger.warning("docling_pdf_fallback_native", filename=filename)
                local_text = self._local.parse_path(path, filename)
                local_fallback = build_text_only_outcome(
                    text_segments=local_text,
                    selected_parser=self._local.__class__.__name__,
                    route="pdf_native_local",
                    reason_codes=["pdf_native_local"],
                )
                return ParseOutcome(
                    text_segments=local_fallback.text_segments,
                    artifacts=local_fallback.artifacts,
                    selected_parser=local_fallback.selected_parser,
                    route="pdf_router",
                    reason_codes=list(decision.reason_codes) + ["docling_failed_fallback_native"],
                    quality_signals=decision.quality_signals,
                    warnings=local_fallback.warnings + ["docling_failed_fallback_native"],
                )

        local_text = self._local.parse_path(path, filename)
        local = build_text_only_outcome(
            text_segments=local_text,
            selected_parser=self._local.__class__.__name__,
            route="pdf_native_local",
            reason_codes=["pdf_native_local"],
        )
        return ParseOutcome(
            text_segments=local.text_segments,
            artifacts=local.artifacts,
            selected_parser=local.selected_parser,
            route="pdf_router",
            reason_codes=list(decision.reason_codes) + ["local_fast"],
            quality_signals=decision.quality_signals,
            warnings=local.warnings,
        )
