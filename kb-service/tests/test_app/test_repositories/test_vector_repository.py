"""Focused tests for VectorRepository search-result shaping.

Runs under the conftest shims (no pgvector C extension, no live DB): we build a
fake sync Engine whose ``begin()`` context yields a connection returning canned
rows, then assert:
  * the search statement encodes score = 1 - cosine_distance (most-similar first)
  * each result is mapped to the API contract dict shape
    {document_id, text, score, metadata}
  * rows without a document_id are dropped
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.models.vector_embedding import VectorEmbedding
from app.repositories.vector_repo import (
    VectorRepository,
    _build_chunk_records,
    _build_lexical_search_statement,
    _build_search_statement,
    _deterministic_chunk_id,
    _map_search_row,
    _merge_hybrid_candidates,
)

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


class _Result:
    def __init__(self, rows=None, row=None, rowcount: int | None = None) -> None:
        self._rows = rows or []
        self._row = row
        self.rowcount = rowcount

    def mappings(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return self._rows


class _Conn:
    def __init__(self, responses: list[_Result]) -> None:
        self._responses = responses
        self.executed: list[str] = []

    def execute(self, statement, params=None):
        self.executed.append(str(statement))
        return self._responses.pop(0)


class _BeginContext:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_map_search_row_renames_columns_to_api_contract() -> None:
    playbook_doc_id = uuid.uuid4()
    kb_doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    mapped = _map_search_row(
        {
            "document_id": playbook_doc_id,
            "kb_service_document_id": kb_doc_id,
            "chunk_id": chunk_id,
            "chunk_index": 7,
            "document": "hello world",
            "cmetadata": {
                "page_index": 2,
                "source_title": "NIL Handbook",
                "priority": 10,
            },
            "score": 0.91,
        }
    )
    assert mapped == {
        "document_id": playbook_doc_id,
        "kb_service_document_id": kb_doc_id,
        "chunk_id": chunk_id,
        "chunk_index": 7,
        "text": "hello world",
        "score": 0.91,
        "metadata": {
            "document_id": str(playbook_doc_id),
            "kb_service_document_id": str(kb_doc_id),
            "kb_document_id": str(kb_doc_id),
            "chunk_id": str(chunk_id),
            "chunk_index": 7,
            "page_index": 2,
            "source_title": "NIL Handbook",
            "priority": 10,
            "score": 0.91,
        },
    }


def test_map_search_row_drops_rows_without_document_id() -> None:
    assert _map_search_row({"document": "x", "score": 0.5}) is None


def test_map_search_row_uses_embedding_row_id_as_legacy_chunk_id_fallback() -> None:
    doc_id = uuid.uuid4()
    embedding_id = uuid.uuid4()

    mapped = _map_search_row(
        {
            "embedding_id": embedding_id,
            "document_id": doc_id,
            "document": "legacy chunk",
            "cmetadata": {"chunk_index": 2},
            "score": 0.8,
        }
    )

    assert mapped is not None
    assert mapped["chunk_id"] == embedding_id
    assert mapped["metadata"]["chunk_id"] == str(embedding_id)
    assert mapped["metadata"]["chunk_index"] == 2


def test_map_search_row_includes_source_summary_when_selected() -> None:
    conversation_file_id = uuid.uuid4()
    kb_doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    mapped = _map_search_row(
        {
            "document_id": conversation_file_id,
            "kb_service_document_id": kb_doc_id,
            "chunk_id": chunk_id,
            "chunk_index": 3,
            "document": "Private contract clause.",
            "source_summary": "A short orientation summary for the contract.",
            "cmetadata": {
                "source_type": "conversation_file",
                "conversation_id": str(uuid.uuid4()),
                "conversation_file_id": str(conversation_file_id),
                "source_locator": {"type": "page", "page_number": 4},
            },
            "score": 0.89,
        }
    )

    assert mapped is not None
    assert mapped["metadata"]["source_type"] == "conversation_file"
    assert mapped["metadata"]["conversation_file_id"] == str(conversation_file_id)
    assert mapped["metadata"]["source_locator"] == {"type": "page", "page_number": 4}
    assert mapped["metadata"]["source_summary"] == (
        "A short orientation summary for the contract."
    )


def test_chunk_records_store_deterministic_citation_metadata() -> None:
    kb_doc_id = uuid.uuid4()
    playbook_doc_id = uuid.uuid4()
    collection_id = uuid.uuid4()
    chunks = [
        {
            "text": "Policy text",
            "metadata": {
                "playbook_document_id": str(playbook_doc_id),
                "source_title": "NIL Handbook",
                "source_date": "2026-01-15",
                "is_official": True,
                "priority": 10,
                "visibility_policy": {"scope": "all_athletes"},
                "organization_id": str(ORG_ID),
                "metadata_tags": {"topic": "nil"},
                "content_type": "application/pdf",
                "page_index": 1,
            },
        }
    ]

    first = _build_chunk_records(
        document_id=kb_doc_id,
        collection_id=collection_id,
        chunks=chunks,
        embeddings=[[0.1] * 1536],
    )[0]
    second = _build_chunk_records(
        document_id=kb_doc_id,
        collection_id=collection_id,
        chunks=chunks,
        embeddings=[[0.2] * 1536],
    )[0]

    metadata = first["cmetadata"]
    assert metadata["document_id"] == str(playbook_doc_id)
    assert metadata["playbook_document_id"] == str(playbook_doc_id)
    assert metadata["kb_service_document_id"] == str(kb_doc_id)
    assert metadata["kb_document_id"] == str(kb_doc_id)
    assert metadata["chunk_index"] == 0
    assert metadata["chunk_id"] == str(_deterministic_chunk_id(kb_doc_id, 0))
    assert second["cmetadata"]["chunk_id"] == metadata["chunk_id"]
    assert metadata["source_title"] == "NIL Handbook"
    assert metadata["visibility_policy"] == {"scope": "all_athletes"}
    assert metadata["organization_id"] == str(ORG_ID)
    assert metadata["metadata_tags"] == {"topic": "nil"}
    assert metadata["page_index"] == 1


def test_chunk_records_store_conversation_file_identity_without_playbook_document_id() -> None:
    kb_doc_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation_file_id = uuid.uuid4()
    records = _build_chunk_records(
        document_id=kb_doc_id,
        collection_id=uuid.uuid4(),
        chunks=[
            {
                "text": "Private contract clause",
                "metadata": {
                    "source_type": "conversation_file",
                    "organization_id": str(ORG_ID),
                    "conversation_id": str(conversation_id),
                    "conversation_file_id": str(conversation_file_id),
                    "source_title": "contract.pdf",
                    "visibility_policy": {"scope": "conversation"},
                    "source_locator": {"type": "page", "page_number": 2},
                },
            }
        ],
        embeddings=[[0.1] * 1536],
    )

    metadata = records[0]["cmetadata"]
    assert metadata["document_id"] == str(conversation_file_id)
    assert metadata["conversation_id"] == str(conversation_id)
    assert metadata["conversation_file_id"] == str(conversation_file_id)
    assert metadata["kb_service_document_id"] == str(kb_doc_id)
    assert metadata["kb_document_id"] == str(kb_doc_id)
    assert metadata["source_type"] == "conversation_file"
    assert metadata["visibility_policy"] == {"scope": "conversation"}
    assert metadata["source_locator"] == {"type": "page", "page_number": 2}
    assert "playbook_document_id" not in metadata


def test_chunk_records_use_global_index_offset_for_batch_metadata() -> None:
    kb_doc_id = uuid.uuid4()
    records = _build_chunk_records(
        document_id=kb_doc_id,
        collection_id=uuid.uuid4(),
        chunks=[{"text": "Batch text", "metadata": {}}],
        embeddings=[[0.1] * 1536],
        chunk_index_offset=12,
    )

    metadata = records[0]["cmetadata"]
    assert metadata["chunk_index"] == 12
    assert metadata["chunk_id"] == str(_deterministic_chunk_id(kb_doc_id, 12))


def test_search_statement_filters_nested_visibility_policy_with_jsonb_containment() -> None:
    metadata_filter = {"visibility_policy": {"scope": "all_athletes"}}

    statement = _build_search_statement(
        collection_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=10,
        score_threshold=0.7,
        organization_id=ORG_ID,
        metadata_filter=metadata_filter,
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    assert "cmetadata @>" in str(compiled)
    assert {"organization_id": str(ORG_ID)} in compiled.params.values()
    assert metadata_filter in compiled.params.values()


def test_search_statement_requires_organization_scope_without_metadata_filter() -> None:
    statement = _build_search_statement(
        collection_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=10,
        score_threshold=0.7,
        organization_id=ORG_ID,
        metadata_filter=None,
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    assert "cmetadata @>" in str(compiled)
    assert {"organization_id": str(ORG_ID)} in compiled.params.values()


def test_search_statement_applies_or_scoped_source_filters() -> None:
    conversation_id = uuid.uuid4()
    metadata_filters = [
        {
            "source_type": "admin_upload",
            "visibility_policy": {"scope": "all_athletes"},
        },
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "visibility_policy": {"scope": "conversation"},
        },
    ]

    statement = _build_search_statement(
        collection_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=10,
        score_threshold=0.7,
        organization_id=ORG_ID,
        metadata_filter=None,
        metadata_filters=metadata_filters,
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert " OR " in sql
    assert {"organization_id": str(ORG_ID)} in compiled.params.values()
    assert metadata_filters[0] in compiled.params.values()
    assert metadata_filters[1] in compiled.params.values()


def test_lexical_search_statement_uses_fts_and_shared_filters() -> None:
    conversation_id = uuid.uuid4()
    metadata_filters = [
        {
            "source_type": "admin_upload",
            "visibility_policy": {"scope": "all_athletes"},
        },
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "visibility_policy": {"scope": "conversation"},
        },
    ]

    statement = _build_lexical_search_statement(
        collection_id=uuid.uuid4(),
        query_text="NIL contract approval",
        max_docs=10,
        organization_id=ORG_ID,
        metadata_filter=None,
        metadata_filters=metadata_filters,
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "websearch_to_tsquery" in sql
    assert "@@" in sql
    assert "ts_rank_cd" in sql
    assert "JOIN kb.documents" in sql
    assert "kb.documents.status = " in sql
    assert " OR " in sql
    assert {"organization_id": str(ORG_ID)} in compiled.params.values()
    assert metadata_filters[0] in compiled.params.values()
    assert metadata_filters[1] in compiled.params.values()


def test_search_statement_only_selects_successful_document_rows() -> None:
    statement = _build_search_statement(
        collection_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=10,
        score_threshold=0.7,
        organization_id=ORG_ID,
        metadata_filter=None,
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "JOIN kb.documents" in sql
    assert "kb.documents.id = CAST(coalesce" in sql
    assert "kb.documents.status = " in sql
    assert "success" in compiled.params.values()


def test_hybrid_merge_returns_vector_only_lexical_only_and_overlap_once() -> None:
    shared_chunk = uuid.uuid4()
    vector_only = uuid.uuid4()
    lexical_only = uuid.uuid4()
    semantic_results = [
        _candidate("shared semantic", shared_chunk, 0.90),
        _candidate("vector only", vector_only, 0.80),
    ]
    lexical_results = [
        _candidate("shared lexical", shared_chunk, 0.70),
        _candidate("lexical only", lexical_only, 0.60),
    ]

    results = _merge_hybrid_candidates(
        semantic_results=semantic_results,
        lexical_results=lexical_results,
        max_docs=10,
        rrf_k=60,
    )

    assert [item["chunk_id"] for item in results] == [
        shared_chunk,
        vector_only,
        lexical_only,
    ]
    assert results[0]["metadata"]["semantic_rank"] == 1
    assert results[0]["metadata"]["lexical_rank"] == 1
    assert results[0]["metadata"]["ranking_strategy"] == "hybrid"
    assert results[1]["metadata"]["lexical_score"] is None
    assert results[2]["metadata"]["semantic_score"] is None


def test_hybrid_merge_dedupes_by_exact_text_when_chunk_id_missing() -> None:
    semantic_results = [
        _candidate("same text", None, 0.90),
    ]
    lexical_results = [
        _candidate("same text", None, 0.75),
    ]

    results = _merge_hybrid_candidates(
        semantic_results=semantic_results,
        lexical_results=lexical_results,
        max_docs=10,
        rrf_k=60,
    )

    assert len(results) == 1
    assert results[0]["metadata"]["semantic_rank"] == 1
    assert results[0]["metadata"]["lexical_rank"] == 1


def test_hybrid_merge_tie_breaks_are_deterministic() -> None:
    first = _candidate("first", uuid.uuid4(), 0.5)
    second = _candidate("second", uuid.uuid4(), 0.5)

    results = _merge_hybrid_candidates(
        semantic_results=[first, second],
        lexical_results=[],
        max_docs=10,
        rrf_k=60,
    )

    assert [item["text"] for item in results] == ["first", "second"]


def test_search_returns_results_ordered_most_similar_first() -> None:
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()
    # Rows are returned by the DB ordered by ascending cosine distance, i.e.
    # descending score (1 - distance). doc_a (score 0.95) precedes doc_b (0.80).
    search_rows = [
        {
            "document_id": doc_a,
            "kb_service_document_id": doc_a,
            "chunk_id": uuid.uuid4(),
            "chunk_index": 1,
            "document": "alpha",
            "cmetadata": {"i": 1},
            "score": 0.95,
        },
        {
            "document_id": doc_b,
            "kb_service_document_id": doc_b,
            "chunk_id": uuid.uuid4(),
            "chunk_index": 2,
            "document": "beta",
            "cmetadata": {"i": 2},
            "score": 0.80,
        },
    ]
    conn = _Conn(
        responses=[
            # resolve_collection_id_for_configuration → SELECT collection_name
            _Result(row={"collection_name": "my-collection"}),
            # get_or_create_collection_id → INSERT ... RETURNING uuid
            _Result(row={"uuid": uuid.uuid4()}),
            # the search SELECT
            _Result(rows=search_rows),
        ]
    )
    fake_engine = SimpleNamespace(begin=lambda: _BeginContext(conn))
    repo = VectorRepository(fake_engine)

    results = repo.search(
        configuration_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=10,
        score_threshold=0.7,
        organization_id=ORG_ID,
    )

    assert [r["document_id"] for r in results] == [doc_a, doc_b]
    assert [r["text"] for r in results] == ["alpha", "beta"]
    assert [r["chunk_index"] for r in results] == [1, 2]
    assert [r["metadata"]["i"] for r in results] == [1, 2]
    # Most similar first → scores are non-increasing.
    assert results[0]["score"] >= results[1]["score"]
    assert set(results[0].keys()) == {
        "document_id",
        "kb_service_document_id",
        "chunk_id",
        "chunk_index",
        "text",
        "score",
        "metadata",
    }


def test_search_dedupes_by_chunk_id_keeps_first_and_caps_results() -> None:
    duplicate_chunk_id = uuid.uuid4()
    unique_chunk_id = uuid.uuid4()
    first_doc = uuid.uuid4()
    later_doc = uuid.uuid4()
    unique_doc = uuid.uuid4()
    search_rows = [
        _search_row(
            document_id=first_doc,
            chunk_id=duplicate_chunk_id,
            chunk_index=1,
            document="first duplicate",
            score=0.95,
        ),
        _search_row(
            document_id=later_doc,
            chunk_id=duplicate_chunk_id,
            chunk_index=2,
            document="later duplicate",
            score=0.99,
        ),
        _search_row(
            document_id=unique_doc,
            chunk_id=unique_chunk_id,
            chunk_index=3,
            document="unique",
            score=0.90,
        ),
    ]
    conn = _Conn(
        responses=[
            _Result(row={"collection_name": "my-collection"}),
            _Result(row={"uuid": uuid.uuid4()}),
            _Result(rows=search_rows),
        ]
    )
    repo = VectorRepository(SimpleNamespace(begin=lambda: _BeginContext(conn)))

    results = repo.search(
        configuration_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=2,
        score_threshold=0.7,
        organization_id=ORG_ID,
    )

    assert [item["document_id"] for item in results] == [first_doc, unique_doc]
    assert [item["text"] for item in results] == ["first duplicate", "unique"]


def test_search_dedupes_by_exact_non_empty_text_when_chunk_id_missing() -> None:
    first_doc = uuid.uuid4()
    later_doc = uuid.uuid4()
    unique_doc = uuid.uuid4()
    search_rows = [
        _search_row(
            document_id=first_doc,
            chunk_id=None,
            chunk_index=None,
            document="same text",
            score=0.95,
        ),
        _search_row(
            document_id=later_doc,
            chunk_id=None,
            chunk_index=None,
            document="same text",
            score=0.99,
        ),
        _search_row(
            document_id=unique_doc,
            chunk_id=None,
            chunk_index=None,
            document="",
            score=0.80,
        ),
        _search_row(
            document_id=uuid.uuid4(),
            chunk_id=None,
            chunk_index=None,
            document="",
            score=0.70,
        ),
    ]
    conn = _Conn(
        responses=[
            _Result(row={"collection_name": "my-collection"}),
            _Result(row={"uuid": uuid.uuid4()}),
            _Result(rows=search_rows),
        ]
    )
    repo = VectorRepository(SimpleNamespace(begin=lambda: _BeginContext(conn)))

    results = repo.search(
        configuration_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=10,
        score_threshold=0.7,
        organization_id=ORG_ID,
    )

    assert [item["document_id"] for item in results] == [
        first_doc,
        unique_doc,
        search_rows[3]["document_id"],
    ]
    assert [item["text"] for item in results] == ["same text", "", ""]


def test_lexical_search_uses_same_result_dedupe_behavior() -> None:
    duplicate_chunk_id = uuid.uuid4()
    first_doc = uuid.uuid4()
    unique_doc = uuid.uuid4()
    search_rows = [
        _search_row(
            document_id=first_doc,
            chunk_id=duplicate_chunk_id,
            chunk_index=1,
            document="first lexical duplicate",
            score=0.95,
        ),
        _search_row(
            document_id=uuid.uuid4(),
            chunk_id=duplicate_chunk_id,
            chunk_index=2,
            document="later lexical duplicate",
            score=0.99,
        ),
        _search_row(
            document_id=unique_doc,
            chunk_id=uuid.uuid4(),
            chunk_index=3,
            document="unique lexical",
            score=0.90,
        ),
    ]
    conn = _Conn(
        responses=[
            _Result(row={"collection_name": "my-collection"}),
            _Result(row={"uuid": uuid.uuid4()}),
            _Result(rows=search_rows),
        ]
    )
    repo = VectorRepository(SimpleNamespace(begin=lambda: _BeginContext(conn)))

    results = repo.lexical_search(
        configuration_id=uuid.uuid4(),
        query_text="nil disclosure",
        max_docs=10,
        organization_id=ORG_ID,
    )

    assert [item["document_id"] for item in results] == [first_doc, unique_doc]
    assert [item["text"] for item in results] == [
        "first lexical duplicate",
        "unique lexical",
    ]


def test_search_returns_empty_for_non_positive_max_docs() -> None:
    fake_engine = SimpleNamespace(begin=lambda: None)
    repo = VectorRepository(fake_engine)
    assert repo.search(
        configuration_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=0,
        score_threshold=0.7,
        organization_id=ORG_ID,
    ) == []


def test_vector_embedding_model_declares_search_vector_column() -> None:
    assert "search_vector" in VectorEmbedding.__table__.columns


def test_phase3_migration_adds_search_vector_and_gin_index() -> None:
    migration = (
        __file__.rsplit("/tests/", maxsplit=1)[0]
        + "/alembic/versions/0003_add_embedding_search_vector.py"
    )
    with open(migration) as migration_file:
        contents = migration_file.read()

    assert "search_vector" in contents
    assert "to_tsvector('english'::regconfig, coalesce(document, ''))" in contents
    assert "USING gin (search_vector)" in contents


def _candidate(
    text: str,
    chunk_id: uuid.UUID | None,
    score: float,
) -> dict:
    return {
        "document_id": uuid.uuid4(),
        "kb_service_document_id": uuid.uuid4(),
        "chunk_id": chunk_id,
        "chunk_index": 0,
        "text": text,
        "score": score,
        "metadata": {
            "chunk_id": str(chunk_id) if chunk_id else None,
            "source_type": "admin_upload",
        },
    }


def _search_row(
    *,
    document_id: uuid.UUID,
    chunk_id: uuid.UUID | None,
    chunk_index: int | None,
    document: str,
    score: float,
) -> dict:
    kb_doc_id = uuid.uuid4()
    metadata = {}
    if chunk_index is not None:
        metadata["chunk_index"] = chunk_index
    if chunk_id is not None:
        metadata["chunk_id"] = str(chunk_id)
    return {
        "document_id": document_id,
        "kb_service_document_id": kb_doc_id,
        "chunk_id": chunk_id,
        "chunk_index": chunk_index,
        "document": document,
        "cmetadata": metadata,
        "score": score,
    }
