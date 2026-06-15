"""Explicit parser extractor catalog used by ParserRouter.

The catalog replaces import-time MIME registration with a small, readable map:
MIME type -> available extractor candidates. Each candidate knows how to invoke
its extractor and returns the common ParseOutcome contract.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Literal, cast

from app.infrastructure.parsers.contracts.base import build_text_only_outcome
from app.infrastructure.parsers.contracts.models import ParseOutcome
from app.infrastructure.parsers.providers.ocr import BaseOCRProvider
from app.infrastructure.parsers.routing.complexity import DOCX_MIME, PDF_MIME, PPTX_MIME

XLS_MIME = "application/vnd.ms-excel"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ExtractorKind = Literal["native", "docling", "ocr"]

if TYPE_CHECKING:
    from app.infrastructure.parsers.extractors.docling import DoclingParserSpec


@dataclass(frozen=True)
class ParseRequest:
    path: str
    filename: str
    mime_type: str
    s3_bucket: str | None = None
    s3_key: str | None = None


@dataclass(frozen=True)
class ExtractorCandidate:
    parser_id: str
    kind: ExtractorKind
    factory: Callable[[], object]

    async def parse(self, request: ParseRequest) -> ParseOutcome | None:
        extractor = self.factory()
        if self.kind == "ocr":
            return await self._parse_ocr(extractor, request)
        return await self._parse_path_extractor(extractor, request)

    async def _parse_ocr(
        self,
        extractor: object,
        request: ParseRequest,
    ) -> ParseOutcome | None:
        parser = cast(BaseOCRProvider, extractor)
        result = parser.parse_pdf_high_complexity(
            path=request.path,
            filename=request.filename,
            s3_bucket=request.s3_bucket,
            s3_key=request.s3_key,
        )
        if inspect.isawaitable(result):
            result = await result
        return result

    async def _parse_path_extractor(
        self,
        extractor: object,
        request: ParseRequest,
    ) -> ParseOutcome | None:
        if hasattr(extractor, "parse_outcome_path"):
            return extractor.parse_outcome_path(request.path, request.filename)
        if hasattr(extractor, "parse_structured_path"):
            return extractor.parse_structured_path(request.path, request.filename)
        if hasattr(extractor, "parse_path"):
            text_segments = extractor.parse_path(request.path, request.filename)
            return build_text_only_outcome(
                text_segments=text_segments,
                selected_parser=self.parser_id,
                route="extractor",
            )
        raise TypeError(f"Extractor {self.parser_id} does not support path parsing")


@dataclass(frozen=True)
class MimeExtractorSet:
    native: ExtractorCandidate
    docling: ExtractorCandidate | None = None
    ocr: ExtractorCandidate | None = None


ExtractorCatalog = Mapping[str, MimeExtractorSet]


def _docling_candidate(
    *,
    spec: "DoclingParserSpec",
) -> ExtractorCandidate:
    from app.infrastructure.parsers.extractors.docling import DoclingParser

    return ExtractorCandidate(
        parser_id=spec.parser_id,
        kind="docling",
        factory=partial(DoclingParser, spec),
    )


def build_default_extractor_catalog(
    *,
    ocr_provider: BaseOCRProvider,
) -> dict[str, MimeExtractorSet]:
    """Build the explicit MIME -> extractor candidate catalog."""
    from app.infrastructure.parsers.extractors.docling import (
        DOCLING_DOCX_SPEC,
        DOCLING_PDF_SPEC,
        DOCLING_PPTX_SPEC,
    )
    from app.infrastructure.parsers.extractors.docx import NativeDOCXParser
    from app.infrastructure.parsers.extractors.excel import NativeExcelParser
    from app.infrastructure.parsers.extractors.pdf import NativePDFParser
    from app.infrastructure.parsers.extractors.pptx import NativePPTXParser

    native_pdf = ExtractorCandidate(
        parser_id="native_pdf",
        kind="native",
        factory=NativePDFParser,
    )
    native_excel = ExtractorCandidate(
        parser_id="native_excel",
        kind="native",
        factory=NativeExcelParser,
    )

    return {
        PDF_MIME: MimeExtractorSet(
            native=native_pdf,
            docling=_docling_candidate(
                spec=DOCLING_PDF_SPEC,
            ),
            ocr=ExtractorCandidate(
                parser_id="ocr_pdf",
                kind="ocr",
                factory=lambda: ocr_provider,
            ),
        ),
        DOCX_MIME: MimeExtractorSet(
            native=ExtractorCandidate(
                parser_id="native_docx",
                kind="native",
                factory=NativeDOCXParser,
            ),
            docling=_docling_candidate(
                spec=DOCLING_DOCX_SPEC,
            ),
        ),
        PPTX_MIME: MimeExtractorSet(
            native=ExtractorCandidate(
                parser_id="native_pptx",
                kind="native",
                factory=NativePPTXParser,
            ),
            docling=_docling_candidate(
                spec=DOCLING_PPTX_SPEC,
            ),
        ),
        XLS_MIME: MimeExtractorSet(native=native_excel),
        XLSX_MIME: MimeExtractorSet(native=native_excel),
    }


def has_usable_text(outcome: ParseOutcome) -> bool:
    return any(
        isinstance(segment, str) and segment.strip()
        for segment in outcome.text_segments
    )
