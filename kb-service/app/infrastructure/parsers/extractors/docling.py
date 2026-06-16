"""Docling-backed parsers for complex documents.

Docling is the "medium complexity" extractor: it produces normalized text plus
structured artifacts (tables as markdown, figure captions, layout blocks). All
``from docling...`` imports are kept INSIDE functions/methods (lazy import) so
this module compiles and imports cleanly even when docling is not installed —
the heavy dependency is only pulled in when a document is actually routed here.

Key pattern: ``parse_outcome_path`` does a single-pass extraction and then
explicitly drops references to the Docling document and runs ``gc.collect()``
before returning, because Docling holds the entire document model in RAM
(100-500 MB for medium PDFs). Releasing it early keeps peak memory bounded
before downstream pipeline stages run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import structlog

from app.core.config import settings
from app.infrastructure.parsers.contracts.errors import CorruptFileError
from app.infrastructure.parsers.contracts.models import ParseArtifacts, ParseOutcome

logger = structlog.get_logger(__name__)

DoclingInputFormat = Literal["pdf", "docx", "pptx"]


@dataclass(frozen=True, slots=True)
class DoclingParserSpec:
    """Static identity and routing metadata for one Docling parser variant."""

    input_format: DoclingInputFormat
    parser_id: str
    parser_name: str
    route: str


DOCLING_PDF_SPEC = DoclingParserSpec(
    input_format="pdf",
    parser_id="docling_pdf",
    parser_name="DoclingPDFParser",
    route="docling_pdf",
)
DOCLING_DOCX_SPEC = DoclingParserSpec(
    input_format="docx",
    parser_id="docling_docx",
    parser_name="DoclingDOCXParser",
    route="docling_docx",
)
DOCLING_PPTX_SPEC = DoclingParserSpec(
    input_format="pptx",
    parser_id="docling_pptx",
    parser_name="DoclingPPTXParser",
    route="docling_pptx",
)


def _resolved_table_mode() -> str:
    profile = settings.DOCLING_TUNING_PROFILE.lower()
    if profile == "speed":
        return "fast"
    if profile == "quality":
        return "accurate"
    return "fast"


def _resolved_images_scale() -> float:
    profile = settings.DOCLING_TUNING_PROFILE.lower()
    if profile == "speed":
        return min(settings.DOCLING_IMAGES_SCALE, 1.0)
    if profile == "quality":
        return max(settings.DOCLING_IMAGES_SCALE, 1.5)
    return min(max(settings.DOCLING_IMAGES_SCALE, 1.0), 1.25)


def _resolved_timeout_seconds() -> float:
    profile = settings.DOCLING_TUNING_PROFILE.lower()
    if profile == "speed":
        return min(settings.DOCLING_TIMEOUT_SECONDS, 90.0)
    if profile == "quality":
        return max(settings.DOCLING_TIMEOUT_SECONDS, 120.0)
    return min(max(settings.DOCLING_TIMEOUT_SECONDS, 90.0), 120.0)


def _build_accelerator_options() -> Any | None:
    if not settings.DOCLING_ENABLE_ACCELERATION:
        return None
    try:
        from docling.datamodel.accelerator_options import (
            AcceleratorDevice,
            AcceleratorOptions,
        )

        device_map = {
            "auto": AcceleratorDevice.AUTO,
            "cpu": AcceleratorDevice.CPU,
            "cuda": AcceleratorDevice.CUDA,
            "mps": AcceleratorDevice.MPS,
        }
        device = device_map.get(settings.DOCLING_ACCELERATOR_DEVICE.lower(), AcceleratorDevice.AUTO)
        return AcceleratorOptions(
            device=device,
            num_threads=settings.DOCLING_ACCELERATOR_THREADS,
        )
    except Exception:
        logger.warning(
            "docling_accelerator_unavailable",
            requested_device=settings.DOCLING_ACCELERATOR_DEVICE,
        )
        return None


def _build_pdf_pipeline_options() -> Any:
    from docling.datamodel.pipeline_options import (
        EasyOcrOptions,
        PdfPipelineOptions,
        TableFormerMode,
    )

    options = PdfPipelineOptions()
    options.do_ocr = settings.DOCLING_DO_OCR
    options.do_table_structure = settings.DOCLING_DO_TABLE_STRUCTURE
    options.document_timeout = _resolved_timeout_seconds()
    options.images_scale = _resolved_images_scale()
    if _resolved_table_mode() == "fast":
        options.table_structure_options.mode = TableFormerMode.FAST
    else:
        options.table_structure_options.mode = TableFormerMode.ACCURATE
    options.ocr_options = EasyOcrOptions(lang=[settings.DOCLING_OCR_LANG])
    accelerator_options = _build_accelerator_options()
    if accelerator_options is not None:
        options.accelerator_options = accelerator_options
    return options


def _build_converter() -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import (
        DocumentConverter,
        PdfFormatOption,
        PowerpointFormatOption,
        WordFormatOption,
    )

    return DocumentConverter(
        allowed_formats=[
            InputFormat.PDF,
            InputFormat.DOCX,
            InputFormat.PPTX,
        ],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=_build_pdf_pipeline_options()),
            InputFormat.DOCX: WordFormatOption(),
            InputFormat.PPTX: PowerpointFormatOption(),
        },
    )


class DoclingParser:
    """Docling conversion helper configured by parser spec."""

    def __init__(self, spec: DoclingParserSpec, converter: Any | None = None) -> None:
        self._spec = spec
        self._converter = converter or _build_converter()

    def _convert_with_profile(self, *, path: str, filename: str) -> Any:
        max_file_size = settings.DOCLING_MAX_FILE_SIZE_MB * 1024 * 1024
        return self._converter.convert(
            source=path,
            max_num_pages=settings.DOCLING_MAX_PAGES,
            max_file_size=max_file_size,
        )

    def parse_path(self, path: str, filename: str) -> list[str]:
        return self.parse_outcome_path(path, filename).text_segments

    def parse_outcome_path(self, path: str, filename: str) -> ParseOutcome:
        """Convert, extract, then immediately release the Docling document object.

        Docling holds the full document model in RAM after `convert()` —
        typically 100-500 MB for medium PDFs. We do a single-pass extraction
        of everything we need (text segments + layout blocks from one walk
        of iterate_items, plus tables and figures from their dedicated lists)
        and then drop all references to the Docling object so the GC can
        reclaim that memory before the rest of the pipeline runs.
        """
        import gc

        try:
            result = self._convert_with_profile(path=path, filename=filename)
            document = result.document

            # Single-pass extraction to minimise the time we hold the Docling object.
            text_segments, text_segment_locators, artifacts = self._extract_all(document)

            # Release the Docling document explicitly — converter caches and any
            # held parser state can be GC'd before downstream stages run.
            document = None  # noqa: F841 — explicit release
            result = None  # noqa: F841 — explicit release
            gc.collect()

            if not text_segments and not artifacts.layout_blocks and not artifacts.tables:
                raise CorruptFileError(f"No parseable content found in {filename}")
            return ParseOutcome(
                text_segments=text_segments,
                artifacts=artifacts,
                selected_parser=self._spec.parser_id,
                route=self._spec.route,
                text_segment_locators=text_segment_locators,
                reason_codes=[f"{self._spec.parser_id}_selected"],
                quality_signals={
                    "text_segment_count": len(text_segments),
                    "table_count": len(artifacts.tables),
                    "figure_count": len(artifacts.figures),
                    "layout_block_count": len(artifacts.layout_blocks),
                },
            )
        except CorruptFileError:
            raise
        except Exception as exc:
            logger.exception(
                "docling_parse_failed",
                filename=filename,
                parser=self._spec.parser_name,
                error=str(exc),
            )
            raise CorruptFileError(f"Failed to parse with Docling: {filename}") from exc

    @staticmethod
    def _extract_all(document: Any) -> tuple[list[str], list[dict[str, Any]], "ParseArtifacts"]:
        """Single-pass extraction of text segments + layout blocks + artifacts.

        Walks `document.iterate_items()` exactly once (vs the previous two
        walks: once for text_segments, once for layout_blocks), then handles
        tables/figures/origin from their dedicated attributes. Less CPU work
        and same memory peak as the prior version.
        """
        text_segments: list[str] = []
        text_segment_locators: list[dict[str, Any]] = []
        layout_blocks: list[dict[str, Any]] = []

        if hasattr(document, "iterate_items"):
            for idx, (item, level) in enumerate(document.iterate_items()):
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    normalized = text.strip()
                    if normalized:
                        text_segments.append(normalized)
                        text_segment_locators.append(
                            {
                                "type": "layout_block",
                                "block_index": idx,
                                "level": level,
                                "label": getattr(getattr(item, "label", None), "name", ""),
                            }
                        )
                        layout_blocks.append(
                            {
                                "index": idx,
                                "level": level,
                                "label": getattr(getattr(item, "label", None), "name", ""),
                                "text": normalized,
                            }
                        )

        # Fallback: if iterate_items yielded nothing, try markdown export.
        if not text_segments and hasattr(document, "export_to_markdown"):
            markdown_text = document.export_to_markdown()
            if isinstance(markdown_text, str) and markdown_text.strip():
                text_segments.append(markdown_text.strip())
                text_segment_locators.append({"type": "document"})

        # Tables — dedicated attribute on the document.
        tables: list[dict[str, Any]] = []
        for idx, table in enumerate(getattr(document, "tables", []) or []):
            try:
                markdown = table.export_to_markdown(doc=document)
            except Exception:
                markdown = ""
            tables.append({"index": idx, "markdown": markdown})

        # Figures — dedicated attribute on the document.
        figures: list[dict[str, Any]] = []
        for idx, picture in enumerate(getattr(document, "pictures", []) or []):
            try:
                caption = picture.caption_text(document) or ""
            except Exception:
                caption = ""
            figures.append({"index": idx, "caption": caption.strip()})

        # Source refs (small).
        source_refs: list[dict[str, Any]] = []
        origin = getattr(document, "origin", None)
        if origin is not None:
            source_refs.append(
                {
                    "filename": getattr(origin, "filename", ""),
                    "mimetype": getattr(origin, "mimetype", ""),
                    "binary_hash": getattr(origin, "binary_hash", ""),
                }
            )

        return (
            text_segments,
            text_segment_locators,
            ParseArtifacts(
                tables=tables,
                figures=figures,
                layout_blocks=layout_blocks,
                source_refs=source_refs,
            ),
        )
