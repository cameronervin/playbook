"""Token-aware RecursiveCharacterTextSplitter wrapper.

Canonical chunking contract:
  strategy:              token_based_recursive
  chunk_size_tokens:     KB_CHUNK_SIZE_TOKENS
  chunk_overlap_tokens:  KB_CHUNK_OVERLAP_TOKENS
  tokenizer:             KB_CHUNK_TOKENIZER (e.g. cl100k_base)

``RecursiveCharacterTextSplitter`` is imported lazily inside the builder so this
module compiles without ``langchain_text_splitters`` installed.
"""
from __future__ import annotations

from typing import Any, Iterator

from app.core.config import settings

CHUNK_STRATEGY = "token_based_recursive"


def _build_text_splitter():
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=settings.KB_CHUNK_TOKENIZER,
        chunk_size=settings.KB_CHUNK_SIZE_TOKENS,
        chunk_overlap=settings.KB_CHUNK_OVERLAP_TOKENS,
        add_start_index=True,
    )


def _get_cached_splitter():
    """Return the worker-scoped cached splitter, falling back to a fresh
    instance for callers outside a worker (tests, ad-hoc scripts).

    The ``app.workers`` package is provided by another part of the service and
    may not exist in every context, so the import is guarded in try/except —
    when it is absent we just build a fresh splitter.
    """
    try:
        from app.workers.state import worker_state

        if worker_state.text_splitter is not None:
            return worker_state.text_splitter
    except Exception:
        # Worker state may not exist outside a worker process (tests, scripts).
        pass
    return _build_text_splitter()


def _build_chunk_metadata(
    *,
    base_metadata: dict[str, Any],
    source_segment_index: int,
    page_chunk_index: int,
    chunk_index: int,
    page_text: str,
    start_index: int | None,
    source_locator: dict[str, Any] | None = None,
) -> dict[str, Any]:
    locator = dict(source_locator or {})
    page_index = locator.get("page_index", source_segment_index)
    chunk_meta = {
        **base_metadata,
        "chunk_strategy": CHUNK_STRATEGY,
        "chunk_size_tokens": settings.KB_CHUNK_SIZE_TOKENS,
        "chunk_overlap_tokens": settings.KB_CHUNK_OVERLAP_TOKENS,
        "chunk_tokenizer": settings.KB_CHUNK_TOKENIZER,
        "page_index": page_index,
        "source_segment_index": source_segment_index,
        "page_chunk_index": page_chunk_index,
        "chunk_index": chunk_index,
        "source_page_char_length": len(page_text),
    }
    if locator:
        chunk_meta["source_locator"] = locator
    if start_index is not None:
        chunk_meta["start_char_index"] = start_index
    return chunk_meta


def _normalize_page_record(page: Any) -> tuple[str, dict[str, Any] | None]:
    if isinstance(page, str):
        return page, None
    if isinstance(page, dict):
        text = page.get("text")
        if not isinstance(text, str):
            raise TypeError("Segment record text must be a string")
        locator = page.get("source_locator")
        if locator is not None and not isinstance(locator, dict):
            raise TypeError("Segment record source_locator must be a dict")
        return text, locator
    raise TypeError("All page entries must be strings or segment records")


def chunk_pages(pages: list[str], metadata: dict | None = None) -> list[dict]:
    """Split a list of page-text strings into token-based chunks (eager).

    Retained for tests and any caller that needs a materialised list. The
    streaming worker pipeline uses ``iter_chunks_from_pages`` instead.
    """
    return list(iter_chunks_from_pages(pages, metadata))


def iter_chunks_from_pages(pages, metadata: dict | None = None) -> Iterator[dict]:
    """Stream chunks lazily from any iterable of page texts.

    Yields one chunk dict at a time so callers can pipe directly to S3 NDJSON
    upload (or any consumer) without ever holding the full chunks list.

    Each chunk dict matches the contract:
        {"text": str, "metadata": {...}}
    """
    splitter = _get_cached_splitter()
    base_metadata = dict(metadata or {})
    chunk_index = 0
    page_index = -1

    for page_index, page in enumerate(pages):
        page_text, source_locator = _normalize_page_record(page)
        if not page_text.strip():
            continue

        split_docs = splitter.create_documents(
            [page_text],
            metadatas=[{"page_index": page_index}],
        )
        for page_chunk_index, split_doc in enumerate(split_docs):
            chunk_text = split_doc.page_content
            if not chunk_text.strip():
                continue
            start_index = split_doc.metadata.get("start_index")
            start_value = start_index if isinstance(start_index, int) else None
            chunk_metadata = _build_chunk_metadata(
                base_metadata=base_metadata,
                source_segment_index=page_index,
                page_chunk_index=page_chunk_index,
                chunk_index=chunk_index,
                page_text=page_text,
                start_index=start_value,
                source_locator=source_locator,
            )
            yield {"text": chunk_text, "metadata": chunk_metadata}
            chunk_index += 1
