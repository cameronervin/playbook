"""Unified parser router: MIME resolution, complexity decision, extractor plan."""
from __future__ import annotations

import mimetypes
from pathlib import Path

import structlog

from app.core.config import settings
from app.infrastructure.parsers.contracts.errors import (
    CorruptFileError,
    UnsupportedFileTypeError,
)
from app.infrastructure.parsers.contracts.models import ParseOutcome
from app.infrastructure.parsers.providers.ocr import (
    BaseOCRProvider,
    build_ocr_provider,
)
from app.infrastructure.parsers.routing.catalog import (
    ExtractorCandidate,
    ExtractorCatalog,
    MimeExtractorSet,
    ParseRequest,
    build_default_extractor_catalog,
    has_usable_text,
)
from app.infrastructure.parsers.routing.complexity import (
    DOCX_MIME,
    PDF_MIME,
    PPTX_MIME,
    ComplexityAssessor,
    ComplexityDecision,
)

logger = structlog.get_logger(__name__)

PARSER_ROUTER_ROUTE = "parser_router"


def _guess_mime(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    known_mime = {
        ".pdf": PDF_MIME,
        ".docx": DOCX_MIME,
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": PPTX_MIME,
    }.get(suffix)
    if known_mime:
        return known_mime
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _docling_routing_enabled() -> bool:
    return settings.DOCLING_ENABLED and settings.ENABLE_DOCLING_ROUTING


def _selection_code(candidate: ExtractorCandidate, *, fallback: bool) -> str:
    if candidate.kind == "native":
        return "fallback_native" if fallback else "selected_native"
    if candidate.kind == "docling":
        return "selected_docling"
    if candidate.kind == "ocr":
        return "selected_ocr"
    return f"selected_{candidate.kind}"


def _failure_code(candidate: ExtractorCandidate, *, unavailable: bool = False) -> str:
    if candidate.kind == "ocr" and unavailable:
        return "ocr_unavailable"
    return f"{candidate.kind}_failed"


def _with_route_metadata(
    outcome: ParseOutcome,
    *,
    candidate: ExtractorCandidate,
    decision: ComplexityDecision,
    route_reason_codes: list[str],
) -> ParseOutcome:
    return ParseOutcome(
        text_segments=outcome.text_segments,
        artifacts=outcome.artifacts,
        selected_parser=candidate.parser_id,
        route=PARSER_ROUTER_ROUTE,
        reason_codes=list(decision.reason_codes) + route_reason_codes,
        quality_signals=dict(decision.quality_signals) | dict(outcome.quality_signals),
        warnings=list(outcome.warnings),
    )


class ParserRouter:
    """Primary parser router used by parse_task.

    Routing is explicit and single-pass: resolve MIME, assess complexity, build
    an ordered extractor plan, then return the first usable ParseOutcome.
    """

    def __init__(
        self,
        *,
        complexity_assessor: ComplexityAssessor | None = None,
        catalog: ExtractorCatalog | None = None,
        ocr_provider: BaseOCRProvider | None = None,
    ) -> None:
        provider = ocr_provider or build_ocr_provider()
        self._assessor = complexity_assessor or ComplexityAssessor()
        self._catalog = catalog or build_default_extractor_catalog(
            ocr_provider=provider,
        )

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
        extractor_set = self._catalog.get(resolved_mime)
        if extractor_set is None:
            raise UnsupportedFileTypeError(f"Unsupported MIME type: {resolved_mime}")

        decision = self._assessor.assess(
            path=path,
            filename=filename,
            mime_type=resolved_mime,
        )
        request = ParseRequest(
            path=path,
            filename=filename,
            mime_type=resolved_mime,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
        )
        return await self._execute_plan(
            request=request,
            decision=decision,
            plan=self._build_plan(
                mime_type=resolved_mime,
                decision=decision,
                extractor_set=extractor_set,
            ),
        )

    def _build_plan(
        self,
        *,
        mime_type: str,
        decision: ComplexityDecision,
        extractor_set: MimeExtractorSet,
    ) -> list[ExtractorCandidate]:
        if mime_type == PDF_MIME and decision.category == "high":
            return self._without_none([extractor_set.ocr, extractor_set.native])

        if (
            mime_type in {PDF_MIME, DOCX_MIME, PPTX_MIME}
            and decision.category == "medium"
            and _docling_routing_enabled()
        ):
            return self._without_none([extractor_set.docling, extractor_set.native])

        return [extractor_set.native]

    @staticmethod
    def _without_none(
        candidates: list[ExtractorCandidate | None],
    ) -> list[ExtractorCandidate]:
        return [candidate for candidate in candidates if candidate is not None]

    async def _execute_plan(
        self,
        *,
        request: ParseRequest,
        decision: ComplexityDecision,
        plan: list[ExtractorCandidate],
    ) -> ParseOutcome:
        if not plan:
            raise UnsupportedFileTypeError(
                f"No parser configured for MIME type: {request.mime_type}"
            )

        route_reason_codes: list[str] = []
        last_error: Exception | None = None

        for index, candidate in enumerate(plan):
            has_fallback = index < len(plan) - 1
            try:
                outcome = await candidate.parse(request)
            except CorruptFileError as exc:
                if has_fallback:
                    route_reason_codes.append(_failure_code(candidate))
                    last_error = exc
                    logger.warning(
                        "parser_candidate_failed_fallback",
                        parser_id=candidate.parser_id,
                        mime_type=request.mime_type,
                        filename=request.filename,
                        error=str(exc),
                    )
                    continue
                raise

            if outcome is None:
                if has_fallback:
                    route_reason_codes.append(_failure_code(candidate, unavailable=True))
                    continue
                if last_error is not None:
                    raise last_error
                raise UnsupportedFileTypeError(
                    f"Parser {candidate.parser_id} returned no parse outcome"
                )

            if has_usable_text(outcome) or not has_fallback:
                route_reason_codes.append(
                    _selection_code(candidate, fallback=len(route_reason_codes) > 0)
                )
                return _with_route_metadata(
                    outcome,
                    candidate=candidate,
                    decision=decision,
                    route_reason_codes=route_reason_codes,
                )

            route_reason_codes.append(_failure_code(candidate))

        if last_error is not None:
            raise last_error
        raise UnsupportedFileTypeError(
            f"No parser produced an outcome for MIME type: {request.mime_type}"
        )
