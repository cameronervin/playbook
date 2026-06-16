from __future__ import annotations

from types import SimpleNamespace

from app.infrastructure.parsers.extractors.docx import _document_text_and_locator
from app.infrastructure.parsers.extractors.excel import _worksheet_segments
from app.infrastructure.parsers.extractors.pdf import _page_segments_from_document
from app.infrastructure.parsers.extractors.pptx import _slide_segments_from_presentation


class _FakePdfPage:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text


def test_pdf_parser_segments_preserve_original_page_numbers() -> None:
    segments = _page_segments_from_document(
        [_FakePdfPage(" Page one "), _FakePdfPage("   "), _FakePdfPage("Page three")]
    )

    assert segments == [
        (
            "Page one",
            {"type": "page", "page_index": 0, "page_number": 1},
        ),
        (
            "Page three",
            {"type": "page", "page_index": 2, "page_number": 3},
        ),
    ]


def test_docx_parser_preserves_paragraph_range_locator() -> None:
    document = SimpleNamespace(
        paragraphs=[
            SimpleNamespace(text=" Intro "),
            SimpleNamespace(text=""),
            SimpleNamespace(text="Body"),
        ]
    )

    text, locator = _document_text_and_locator(document)

    assert text == "Intro\nBody"
    assert locator == {
        "type": "paragraph_range",
        "paragraph_start": 1,
        "paragraph_end": 3,
    }


def test_pptx_parser_preserves_slide_locator() -> None:
    slide = SimpleNamespace(
        shapes=[
            SimpleNamespace(text=" Title "),
            SimpleNamespace(text="Body"),
        ]
    )
    presentation = SimpleNamespace(slides=[slide])

    assert _slide_segments_from_presentation(presentation) == [
        (
            "# Slide 1\nTitle\nBody",
            {"type": "slide", "slide_index": 0, "slide_number": 1},
        )
    ]


def test_excel_parser_preserves_sheet_and_row_range_locator() -> None:
    worksheet = SimpleNamespace(
        title="Sheet A",
        iter_rows=lambda values_only=True: iter(
            [
                ("Name", "Value"),
                (None, None),
                ("Limit", 10),
            ]
        ),
    )
    workbook = SimpleNamespace(worksheets=[worksheet])

    assert _worksheet_segments(workbook) == [
        (
            "# Sheet A\nName | Value\nLimit | 10",
            {
                "type": "sheet",
                "sheet_index": 0,
                "sheet_name": "Sheet A",
                "row_start": 1,
                "row_end": 3,
            },
        )
    ]
