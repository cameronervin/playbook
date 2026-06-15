from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.infrastructure.parsers.contracts.errors import CorruptFileError
from app.infrastructure.parsers.extractors.docling import (
    DOCLING_PDF_SPEC,
    DoclingParser,
)


class _FakeConverter:
    def __init__(self, document: object) -> None:
        self.document = document
        self.convert_kwargs: dict[str, Any] | None = None

    def convert(self, **kwargs: Any) -> SimpleNamespace:
        self.convert_kwargs = kwargs
        return SimpleNamespace(document=self.document)


class _FakeItem:
    def __init__(self, text: str, label: str) -> None:
        self.text = text
        self.label = SimpleNamespace(name=label)


class _FakeTable:
    def export_to_markdown(self, *, doc: object) -> str:
        return "| Col |\n| --- |\n| Value |"


class _FakePicture:
    def caption_text(self, document: object) -> str:
        return "Figure caption"


class _FakeDocument:
    tables = [_FakeTable()]
    pictures = [_FakePicture()]
    origin = SimpleNamespace(
        filename="policy.pdf",
        mimetype="application/pdf",
        binary_hash="abc123",
    )

    def iterate_items(self):
        return iter(
            [
                (_FakeItem(" Title ", "SECTION_HEADER"), 0),
                (_FakeItem("Body text", "PARAGRAPH"), 1),
                (_FakeItem(" ", "EMPTY"), 1),
            ]
        )


class _EmptyDocument:
    tables: list[object] = []
    pictures: list[object] = []

    def iterate_items(self):
        return iter([])

    def export_to_markdown(self) -> str:
        return "   "


def test_docling_parser_uses_spec_metadata_and_extracts_artifacts() -> None:
    converter = _FakeConverter(_FakeDocument())
    parser = DoclingParser(DOCLING_PDF_SPEC, converter=converter)

    outcome = parser.parse_outcome_path("/tmp/policy.pdf", "policy.pdf")

    assert outcome.text_segments == ["Title", "Body text"]
    assert outcome.selected_parser == "docling_pdf"
    assert outcome.route == "docling_pdf"
    assert outcome.reason_codes == ["docling_pdf_selected"]
    assert outcome.quality_signals == {
        "text_segment_count": 2,
        "table_count": 1,
        "figure_count": 1,
        "layout_block_count": 2,
    }
    assert outcome.artifacts.tables == [
        {"index": 0, "markdown": "| Col |\n| --- |\n| Value |"}
    ]
    assert outcome.artifacts.figures == [
        {"index": 0, "caption": "Figure caption"}
    ]
    assert outcome.artifacts.layout_blocks == [
        {
            "index": 0,
            "level": 0,
            "label": "SECTION_HEADER",
            "text": "Title",
        },
        {
            "index": 1,
            "level": 1,
            "label": "PARAGRAPH",
            "text": "Body text",
        },
    ]
    assert outcome.artifacts.source_refs == [
        {
            "filename": "policy.pdf",
            "mimetype": "application/pdf",
            "binary_hash": "abc123",
        }
    ]
    assert converter.convert_kwargs is not None
    assert converter.convert_kwargs["source"] == "/tmp/policy.pdf"


def test_docling_parser_raises_when_no_parseable_content() -> None:
    parser = DoclingParser(DOCLING_PDF_SPEC, converter=_FakeConverter(_EmptyDocument()))

    with pytest.raises(CorruptFileError):
        parser.parse_outcome_path("/tmp/empty.pdf", "empty.pdf")
