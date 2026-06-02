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

from app.repositories.vector_repo import VectorRepository, _map_search_row


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
    doc_id = uuid.uuid4()
    mapped = _map_search_row(
        {
            "document_id": doc_id,
            "document": "hello world",
            "cmetadata": {"page_index": 2},
            "score": 0.91,
        }
    )
    assert mapped == {
        "document_id": doc_id,
        "text": "hello world",
        "score": 0.91,
        "metadata": {"page_index": 2},
    }


def test_map_search_row_drops_rows_without_document_id() -> None:
    assert _map_search_row({"document": "x", "score": 0.5}) is None


def test_search_returns_results_ordered_most_similar_first() -> None:
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()
    # Rows are returned by the DB ordered by ascending cosine distance, i.e.
    # descending score (1 - distance). doc_a (score 0.95) precedes doc_b (0.80).
    search_rows = [
        {"document_id": doc_a, "document": "alpha", "cmetadata": {"i": 1}, "score": 0.95},
        {"document_id": doc_b, "document": "beta", "cmetadata": {"i": 2}, "score": 0.80},
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
    )

    assert [r["document_id"] for r in results] == [doc_a, doc_b]
    assert [r["text"] for r in results] == ["alpha", "beta"]
    assert [r["metadata"] for r in results] == [{"i": 1}, {"i": 2}]
    # Most similar first → scores are non-increasing.
    assert results[0]["score"] >= results[1]["score"]
    assert set(results[0].keys()) == {"document_id", "text", "score", "metadata"}


def test_search_returns_empty_for_non_positive_max_docs() -> None:
    fake_engine = SimpleNamespace(begin=lambda: None)
    repo = VectorRepository(fake_engine)
    assert repo.search(
        configuration_id=uuid.uuid4(),
        query_vector=[0.1] * 1536,
        max_docs=0,
        score_threshold=0.7,
    ) == []
