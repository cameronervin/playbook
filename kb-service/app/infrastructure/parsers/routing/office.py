"""Office router strategy for DOCX/PPTX complexity-based routing.

    medium -> Docling DOCX/PPTX parser (structured extraction), with a fallback
              to the supplied native parser if Docling fails.
    low    -> the native parser passed in by the top-level router.

Docling parsers are constructed lazily (only when a medium-complexity document
is actually routed) so importing this module never pulls docling in.
"""
from __future__ import annotations

import structlog

from app.core.config import settings
from app.infrastructure.parsers.contracts.base import IParser, build_text_only_outcome
from app.infrastructure.parsers.contracts.models import ParseOutcome
from app.infrastructure.parsers.extractors.docling import DoclingDOCXParser, DoclingPPTXParser
from app.infrastructure.parsers.routing.complexity import (
    DOCX_MIME,
    PPTX_MIME,
    ComplexityAssessor,
    ComplexityDecision,
)

logger = structlog.get_logger(__name__)


class OfficeRouter:
    """Encapsulates DOCX/PPTX complexity routing and fallback handling."""

    def __init__(
        self,
        complexity_assessor: ComplexityAssessor | None = None,
        docling_docx: DoclingDOCXParser | None = None,
        docling_pptx: DoclingPPTXParser | None = None,
    ) -> None:
        self._assessor = complexity_assessor or ComplexityAssessor()
        self._docling_docx = docling_docx
        self._docling_pptx = docling_pptx

    def route_path(
        self,
        *,
        parser: IParser,
        path: str,
        filename: str,
        mime_type: str,
    ) -> ParseOutcome:
        decision = self._assessor.assess(path=path, filename=filename, mime_type=mime_type)
        if decision.category == "medium" and settings.DOCLING_ENABLED:
            return self._parse_complex(
                parser=parser,
                path=path,
                filename=filename,
                mime_type=mime_type,
                decision=decision,
            )
        return self._parse_local(parser=parser, path=path, filename=filename, decision=decision)

    def _parse_complex(
        self,
        *,
        parser: IParser,
        path: str,
        filename: str,
        mime_type: str,
        decision: ComplexityDecision,
    ) -> ParseOutcome:
        docling_parser = self._get_docling_parser(mime_type)
        try:
            outcome = docling_parser.parse_structured_path(path, filename)
            return ParseOutcome(
                text_segments=outcome.text_segments,
                artifacts=outcome.artifacts,
                selected_parser=outcome.selected_parser,
                route="complexity_router",
                reason_codes=list(decision.reason_codes) + ["docling_complex_route"],
                quality_signals=decision.quality_signals | outcome.quality_signals,
                warnings=outcome.warnings,
            )
        except Exception:
            logger.warning("office_docling_fallback_local", filename=filename, mime_type=mime_type)
            local_outcome = self._parse_with_local_parser(parser=parser, path=path, filename=filename)
            return ParseOutcome(
                text_segments=local_outcome.text_segments,
                artifacts=local_outcome.artifacts,
                selected_parser=local_outcome.selected_parser,
                route="complexity_router",
                reason_codes=list(decision.reason_codes) + ["docling_failed_fallback_local"],
                quality_signals=decision.quality_signals,
                warnings=local_outcome.warnings + ["docling_failed_fallback_local"],
            )

    def _parse_local(
        self,
        *,
        parser: IParser,
        path: str,
        filename: str,
        decision: ComplexityDecision,
    ) -> ParseOutcome:
        local_outcome = self._parse_with_local_parser(parser=parser, path=path, filename=filename)
        return ParseOutcome(
            text_segments=local_outcome.text_segments,
            artifacts=local_outcome.artifacts,
            selected_parser=local_outcome.selected_parser,
            route="complexity_router",
            reason_codes=list(decision.reason_codes) + ["local_simple_route"],
            quality_signals=decision.quality_signals,
            warnings=local_outcome.warnings,
        )

    @staticmethod
    def _parse_with_local_parser(*, parser: IParser, path: str, filename: str) -> ParseOutcome:
        return build_text_only_outcome(
            text_segments=parser.parse_path(path, filename),
            selected_parser=parser.__class__.__name__,
            route="direct_path",
            reason_codes=["path_parse"],
        )

    def _get_docling_parser(self, mime_type: str):
        if mime_type == DOCX_MIME:
            if self._docling_docx is None:
                self._docling_docx = DoclingDOCXParser()
            return self._docling_docx
        if mime_type == PPTX_MIME:
            if self._docling_pptx is None:
                self._docling_pptx = DoclingPPTXParser()
            return self._docling_pptx
        raise ValueError(f"Unsupported office MIME for OfficeRouter: {mime_type}")
