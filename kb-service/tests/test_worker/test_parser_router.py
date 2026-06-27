from __future__ import annotations

from collections.abc import Callable

import pytest

from app.core.config import settings
from app.infrastructure.parsers.contracts.errors import (
    CorruptFileError,
    UnsupportedFileTypeError,
)
from app.infrastructure.parsers.contracts.models import ParseArtifacts, ParseOutcome
from app.infrastructure.parsers.providers.ocr import NullOCRProvider
from app.infrastructure.parsers.routing.catalog import (
    ExtractorCandidate,
    MimeExtractorSet,
    build_default_extractor_catalog,
)
from app.infrastructure.parsers.routing.complexity import (
    DOCX_MIME,
    PDF_MIME,
    PPTX_MIME,
    ComplexityDecision,
)
from app.infrastructure.parsers.routing.router import ParserRouter

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class _FakeAssessor:
    def __init__(self, category: str) -> None:
        self.category = category

    def assess(self, *, path: str, filename: str, mime_type: str) -> ComplexityDecision:
        return ComplexityDecision(
            category=self.category,
            reason_codes=[f"{mime_type}_is_{self.category}"],
            quality_signals={"complexity": self.category},
        )


class _OutcomeParser:
    def __init__(self, parser_id: str, *, fail: bool = False) -> None:
        self.parser_id = parser_id
        self.fail = fail

    def parse_outcome_path(self, path: str, filename: str) -> ParseOutcome:
        if self.fail:
            raise CorruptFileError(f"{self.parser_id} failed")
        return ParseOutcome(
            text_segments=[f"{self.parser_id} text"],
            artifacts=ParseArtifacts(),
            selected_parser=f"raw_{self.parser_id}",
            route="raw_extractor",
            reason_codes=["raw_reason"],
            quality_signals={"extractor": self.parser_id},
        )


class _UnavailableOCR:
    provider = "none"

    async def parse_pdf_high_complexity(self, **kwargs) -> ParseOutcome | None:
        return None


class _AvailableOCR:
    provider = "vlm"

    async def parse_pdf_high_complexity(self, **kwargs) -> ParseOutcome | None:
        return ParseOutcome(
            text_segments=["ocr text"],
            artifacts=ParseArtifacts(),
            selected_parser="vlm_ocr_pdf",
            route="vlm_ocr",
            reason_codes=["vlm_ocr_selected"],
            quality_signals={"extractor": "vlm_ocr_pdf"},
        )


def _candidate(
    parser_id: str,
    kind: str,
    factory: Callable[[], object] | None = None,
) -> ExtractorCandidate:
    return ExtractorCandidate(
        parser_id=parser_id,
        kind=kind,
        factory=factory or (lambda: _OutcomeParser(parser_id)),
    )


def _router_for(
    *,
    category: str,
    catalog: dict[str, MimeExtractorSet],
) -> ParserRouter:
    return ParserRouter(
        complexity_assessor=_FakeAssessor(category),
        catalog=catalog,
    )


def test_default_catalog_uses_canonical_native_modules_and_classes() -> None:
    catalog = build_default_extractor_catalog(ocr_provider=NullOCRProvider())

    native_cases = [
        (PDF_MIME, "app.infrastructure.parsers.extractors.pdf", "NativePDFParser"),
        (DOCX_MIME, "app.infrastructure.parsers.extractors.docx", "NativeDOCXParser"),
        (PPTX_MIME, "app.infrastructure.parsers.extractors.pptx", "NativePPTXParser"),
        (XLSX_MIME, "app.infrastructure.parsers.extractors.excel", "NativeExcelParser"),
    ]

    for mime_type, module_name, class_name in native_cases:
        extractor = catalog[mime_type].native.factory()

        assert extractor.__class__.__module__ == module_name
        assert extractor.__class__.__name__ == class_name


@pytest.mark.asyncio
async def test_pdf_low_complexity_selects_native_pdf() -> None:
    router = _router_for(
        category="low",
        catalog={
            PDF_MIME: MimeExtractorSet(
                native=_candidate("native_pdf", "native"),
                docling=_candidate("docling_pdf", "docling"),
                ocr=_candidate("ocr_pdf", "ocr", lambda: _UnavailableOCR()),
            )
        },
    )

    outcome = await router.route_path(path="/tmp/simple.pdf", filename="simple.pdf")

    assert outcome.selected_parser == "native_pdf"
    assert outcome.route == "parser_router"
    assert outcome.reason_codes == [f"{PDF_MIME}_is_low", "selected_native"]
    assert outcome.quality_signals == {"complexity": "low", "extractor": "native_pdf"}


@pytest.mark.asyncio
async def test_pdf_medium_complexity_selects_docling_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DOCLING_ENABLED", True)
    monkeypatch.setattr(settings, "ENABLE_DOCLING_ROUTING", True)
    router = _router_for(
        category="medium",
        catalog={
            PDF_MIME: MimeExtractorSet(
                native=_candidate("native_pdf", "native"),
                docling=_candidate("docling_pdf", "docling"),
                ocr=_candidate("ocr_pdf", "ocr", lambda: _UnavailableOCR()),
            )
        },
    )

    outcome = await router.route_path(path="/tmp/structured.pdf", filename="structured.pdf")

    assert outcome.selected_parser == "docling_pdf"
    assert outcome.reason_codes == [f"{PDF_MIME}_is_medium", "selected_docling"]


@pytest.mark.asyncio
async def test_pdf_medium_docling_failure_falls_back_to_native_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DOCLING_ENABLED", True)
    monkeypatch.setattr(settings, "ENABLE_DOCLING_ROUTING", True)
    router = _router_for(
        category="medium",
        catalog={
            PDF_MIME: MimeExtractorSet(
                native=_candidate("native_pdf", "native"),
                docling=_candidate(
                    "docling_pdf",
                    "docling",
                    lambda: _OutcomeParser("docling_pdf", fail=True),
                ),
                ocr=_candidate("ocr_pdf", "ocr", lambda: _UnavailableOCR()),
            )
        },
    )

    outcome = await router.route_path(path="/tmp/structured.pdf", filename="structured.pdf")

    assert outcome.selected_parser == "native_pdf"
    assert outcome.reason_codes == [
        f"{PDF_MIME}_is_medium",
        "docling_failed",
        "fallback_native",
    ]


@pytest.mark.asyncio
async def test_pdf_high_unavailable_ocr_falls_back_to_native_pdf() -> None:
    router = _router_for(
        category="high",
        catalog={
            PDF_MIME: MimeExtractorSet(
                native=_candidate("native_pdf", "native"),
                docling=_candidate("docling_pdf", "docling"),
                ocr=_candidate("ocr_pdf", "ocr", lambda: _UnavailableOCR()),
            )
        },
    )

    outcome = await router.route_path(path="/tmp/scanned.pdf", filename="scanned.pdf")

    assert outcome.selected_parser == "native_pdf"
    assert outcome.reason_codes == [
        f"{PDF_MIME}_is_high",
        "ocr_unavailable",
        "fallback_native",
    ]


@pytest.mark.asyncio
async def test_pdf_high_available_ocr_selects_ocr() -> None:
    router = _router_for(
        category="high",
        catalog={
            PDF_MIME: MimeExtractorSet(
                native=_candidate("native_pdf", "native"),
                docling=_candidate("docling_pdf", "docling"),
                ocr=_candidate("ocr_pdf", "ocr", lambda: _AvailableOCR()),
            )
        },
    )

    outcome = await router.route_path(path="/tmp/scanned.pdf", filename="scanned.pdf")

    assert outcome.selected_parser == "ocr_pdf"
    assert outcome.reason_codes == [
        f"{PDF_MIME}_is_high",
        "selected_ocr",
    ]
    assert outcome.quality_signals == {"complexity": "high", "extractor": "vlm_ocr_pdf"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mime_type", "native_id", "docling_id", "filename"),
    [
        (DOCX_MIME, "native_docx", "docling_docx", "rules.docx"),
        (PPTX_MIME, "native_pptx", "docling_pptx", "deck.pptx"),
    ],
)
async def test_office_low_complexity_selects_native(
    mime_type: str,
    native_id: str,
    docling_id: str,
    filename: str,
) -> None:
    router = _router_for(
        category="low",
        catalog={
            mime_type: MimeExtractorSet(
                native=_candidate(native_id, "native"),
                docling=_candidate(docling_id, "docling"),
            )
        },
    )

    outcome = await router.route_path(
        path=f"/tmp/{filename}",
        filename=filename,
        mime_type=mime_type,
    )

    assert outcome.selected_parser == native_id
    assert outcome.reason_codes == [f"{mime_type}_is_low", "selected_native"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mime_type", "native_id", "docling_id", "filename"),
    [
        (DOCX_MIME, "native_docx", "docling_docx", "rules.docx"),
        (PPTX_MIME, "native_pptx", "docling_pptx", "deck.pptx"),
    ],
)
async def test_office_medium_complexity_selects_docling_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    mime_type: str,
    native_id: str,
    docling_id: str,
    filename: str,
) -> None:
    monkeypatch.setattr(settings, "DOCLING_ENABLED", True)
    monkeypatch.setattr(settings, "ENABLE_DOCLING_ROUTING", True)
    router = _router_for(
        category="medium",
        catalog={
            mime_type: MimeExtractorSet(
                native=_candidate(native_id, "native"),
                docling=_candidate(docling_id, "docling"),
            )
        },
    )

    outcome = await router.route_path(
        path=f"/tmp/{filename}",
        filename=filename,
        mime_type=mime_type,
    )

    assert outcome.selected_parser == docling_id
    assert outcome.reason_codes == [f"{mime_type}_is_medium", "selected_docling"]


@pytest.mark.asyncio
async def test_excel_selects_native_excel() -> None:
    router = _router_for(
        category="low",
        catalog={
            XLSX_MIME: MimeExtractorSet(
                native=_candidate("native_excel", "native"),
            )
        },
    )

    outcome = await router.route_path(
        path="/tmp/roster.xlsx",
        filename="roster.xlsx",
        mime_type=XLSX_MIME,
    )

    assert outcome.selected_parser == "native_excel"
    assert outcome.reason_codes == [f"{XLSX_MIME}_is_low", "selected_native"]


@pytest.mark.asyncio
async def test_unsupported_mime_raises() -> None:
    router = _router_for(category="low", catalog={})

    with pytest.raises(UnsupportedFileTypeError):
        await router.route_path(
            path="/tmp/file.bin",
            filename="file.bin",
            mime_type="application/octet-stream",
        )
