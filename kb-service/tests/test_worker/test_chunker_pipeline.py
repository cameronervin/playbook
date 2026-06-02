"""Tests for the streaming token-based chunker (worker pipeline chunk stage).

Runs under the conftest langchain_text_splitters shim — no tiktoken / native
splitter required. Verifies ``iter_chunks_from_pages`` yields the canonical
chunk contract: {"text": str, "metadata": {...}} with stable, contiguous
chunk_index values and the expected metadata keys.
"""
from __future__ import annotations

import pytest

from app.infrastructure.chunkers.token_based import (
    CHUNK_STRATEGY,
    chunk_pages,
    iter_chunks_from_pages,
)


def test_iter_chunks_yields_text_and_metadata_contract() -> None:
    pages = [" ".join(["alpha"] * 400), " ".join(["beta"] * 400)]
    metadata = {"document_id": "doc-1", "source": "unit-test"}

    chunks = list(iter_chunks_from_pages(pages, metadata))

    assert chunks, "expected at least one chunk"
    for chunk in chunks:
        assert set(chunk.keys()) == {"text", "metadata"}
        assert isinstance(chunk["text"], str) and chunk["text"].strip()
        meta = chunk["metadata"]
        # Required metadata keys.
        assert "chunk_index" in meta
        assert "page_index" in meta
        assert meta["chunk_strategy"] == CHUNK_STRATEGY
        # Base metadata is propagated.
        assert meta["document_id"] == "doc-1"
        assert meta["source"] == "unit-test"


def test_chunk_index_is_contiguous_and_zero_based() -> None:
    pages = [" ".join(["alpha"] * 400), " ".join(["beta"] * 400)]
    chunks = list(iter_chunks_from_pages(pages, {"document_id": "doc-1"}))

    indices = [c["metadata"]["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks)))


def test_page_index_tracks_source_page() -> None:
    pages = [" ".join(["alpha"] * 400), " ".join(["beta"] * 400)]
    chunks = list(iter_chunks_from_pages(pages, {"document_id": "doc-1"}))

    page_indices = {c["metadata"]["page_index"] for c in chunks}
    # Both non-empty pages should contribute at least one chunk.
    assert page_indices == {0, 1}


def test_chunk_pages_is_deterministic_and_does_not_mutate_metadata() -> None:
    pages = [" ".join(["alpha"] * 400)]
    metadata = {"document_id": "doc-1", "source": "unit-test"}

    first = chunk_pages(pages, metadata)
    second = chunk_pages(pages, metadata)

    assert [c["text"] for c in first] == [c["text"] for c in second]
    # The caller's metadata dict must not be mutated.
    assert metadata == {"document_id": "doc-1", "source": "unit-test"}


def test_empty_and_blank_pages_produce_no_chunks() -> None:
    assert chunk_pages([]) == []
    assert chunk_pages(["   ", "\n", "\t"]) == []


def test_non_string_page_raises_type_error() -> None:
    with pytest.raises(TypeError):
        list(iter_chunks_from_pages(["valid page", 123], {"document_id": "doc-1"}))
