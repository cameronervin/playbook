from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.workers.tasks import summary


def test_select_summary_indices_is_deterministic_and_bounded() -> None:
    first = summary._select_summary_indices(100, max_chunks=8)
    second = summary._select_summary_indices(100, max_chunks=8)

    assert first == second
    assert first[0] == 0
    assert first[-1] == 99
    assert len(first) <= 8


def test_summary_source_from_document_preserves_source_metadata() -> None:
    document_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        name="contract.pdf",
        summary=None,
        metadata_={
            "source_type": "conversation_file",
            "source_title": "Contract",
            "conversation_id": str(uuid4()),
            "conversation_file_id": str(uuid4()),
        },
    )
    parse_result = {"selected_parser": "native_pdf", "route": "native"}
    chunks = [{"text": "Private contract clause.", "metadata": {"chunk_index": 0}}]

    source = summary._summary_source_from_document(
        document=document,
        parse_result=parse_result,
        chunks=chunks,
    )

    assert source.filename == "contract.pdf"
    assert source.source_title == "Contract"
    assert source.metadata["source_type"] == "conversation_file"
    assert source.parse_result == parse_result
    assert source.chunks == chunks
