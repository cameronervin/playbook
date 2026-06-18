from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure.rerankers.base import RerankCandidate, RerankedCandidate
from app.schemas.search import SearchRequest
from app.services.configuration_service import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_CONFIGURATION_NAME,
)
from app.services.search_service import SearchService


class FakeConfigurationService:
    def __init__(self) -> None:
        self.resolve_calls = 0
        now = datetime.now(UTC)
        self.config = SimpleNamespace(
            id=uuid4(),
            name=DEFAULT_CONFIGURATION_NAME,
            collection_name=DEFAULT_COLLECTION_NAME,
            version=1,
            parse_config={},
            chunk_config={},
            embed_config={},
            vectorstore_config={},
            created_at=now,
            updated_at=now,
        )

    async def resolve(self, data=None) -> SimpleNamespace:
        self.resolve_calls += 1
        return self.config


class FakeEmbedProvider:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.requests: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.requests.append(texts)
        return self.vectors


class FakeVectorRepository:
    def __init__(
        self,
        *,
        fail_hybrid: bool = False,
        search_results: list[dict] | None = None,
        hybrid_results: list[dict] | None = None,
    ) -> None:
        self.requests: list[dict] = []
        self.hybrid_requests: list[dict] = []
        self.fail_hybrid = fail_hybrid
        self.search_results = search_results or []
        self.hybrid_results = hybrid_results or _default_hybrid_results()

    async def search(self, **kwargs) -> list[dict]:
        self.requests.append(kwargs)
        return self.search_results[: kwargs.get("max_docs", len(self.search_results))]

    async def hybrid_search(self, **kwargs) -> list[dict]:
        self.hybrid_requests.append(kwargs)
        if self.fail_hybrid:
            raise RuntimeError("lexical path failed")
        return self.hybrid_results[: kwargs.get("final_limit", len(self.hybrid_results))]


class FakeRerankProvider:
    provider_name = "fake"

    def __init__(
        self,
        *,
        reranked_indexes: list[int] | None = None,
        scores: list[float | None] | None = None,
    ) -> None:
        self.requests: list[dict] = []
        self.reranked_indexes = reranked_indexes or []
        self.scores = scores or []

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RerankCandidate],
        top_n: int | None = None,
    ) -> list[RerankedCandidate]:
        self.requests.append(
            {
                "query": query,
                "candidates": candidates,
                "top_n": top_n,
            }
        )
        indexes = self.reranked_indexes or list(range(len(candidates)))
        if top_n is not None:
            indexes = indexes[:top_n]
        return [
            RerankedCandidate(
                candidate=candidates[index],
                rerank_score=self.scores[offset]
                if offset < len(self.scores)
                else None,
                rank=offset + 1,
            )
            for offset, index in enumerate(indexes)
        ]


class FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _hybrid_result(
    *,
    text: str,
    hybrid_score: float,
    semantic_rank: int | None,
    lexical_rank: int | None,
    chunk_id: object | None = None,
) -> dict:
    semantic_score = None if semantic_rank is None else 1.0 - (semantic_rank * 0.1)
    lexical_score = None if lexical_rank is None else 0.9 - (lexical_rank * 0.1)
    resolved_chunk_id = chunk_id if chunk_id is not None else uuid4()
    return {
        "document_id": uuid4(),
        "kb_service_document_id": uuid4(),
        "chunk_id": resolved_chunk_id,
        "chunk_index": 0,
        "text": text,
        "score": hybrid_score,
        "metadata": {
            "semantic_score": semantic_score,
            "semantic_rank": semantic_rank,
            "lexical_score": lexical_score,
            "lexical_rank": lexical_rank,
            "hybrid_score": hybrid_score,
            "rerank_score": None,
            "ranking_strategy": "hybrid",
            "chunk_id": str(resolved_chunk_id),
        },
    }


def _default_hybrid_results() -> list[dict]:
    return [
        _hybrid_result(
            text="Hybrid first result",
            hybrid_score=0.05,
            semantic_rank=1,
            lexical_rank=2,
        ),
        _hybrid_result(
            text="Hybrid second result",
            hybrid_score=0.04,
            semantic_rank=2,
            lexical_rank=1,
        ),
        _hybrid_result(
            text="Hybrid third result",
            hybrid_score=0.03,
            semantic_rank=3,
            lexical_rank=None,
        ),
    ]


def _search_result(
    *,
    text: str,
    score: float,
    chunk_id: str | None = None,
) -> dict:
    return {
        "document_id": uuid4(),
        "kb_service_document_id": uuid4(),
        "chunk_id": chunk_id,
        "chunk_index": 0,
        "text": text,
        "score": score,
        "metadata": {"chunk_id": chunk_id} if chunk_id is not None else {},
    }


@pytest.fixture(autouse=True)
def default_semantic_search_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.search_service.settings.KB_SEARCH_STRATEGY",
        "semantic",
    )
    monkeypatch.setattr(
        "app.services.search_service.settings.KB_RERANK_ENABLED",
        False,
    )


@pytest.mark.asyncio
async def test_search_resolves_default_configuration_before_vector_search() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    organization_id = uuid4()

    response = await service.search(
        SearchRequest(
            query="nil disclosure",
            organization_id=organization_id,
            visibility_context={"role": "athlete"},
        )
    )

    assert response.total == 0
    assert config_service.resolve_calls == 1
    assert vector_repo.requests[0]["configuration_id"] == config_service.config.id
    assert vector_repo.requests[0]["metadata_filters"] == [
        {
            "source_type": "admin_upload",
            "visibility_policy": {"scope": "all_athletes"},
        }
    ]


@pytest.mark.asyncio
async def test_search_returns_zero_results_for_fresh_default_without_vectors() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(query="compliance", organization_id=uuid4())
    )

    assert response.results == []
    assert response.total == 0
    assert config_service.resolve_calls == 1
    assert vector_repo.requests == []


@pytest.mark.asyncio
async def test_semantic_search_returns_unique_chunks_in_repository_order() -> None:
    duplicate_chunk_id = str(uuid4())
    search_results = [
        _search_result(
            text="First duplicate from semantic search.",
            score=0.91,
            chunk_id=duplicate_chunk_id,
        ),
        _search_result(
            text="Later duplicate from semantic search.",
            score=0.99,
            chunk_id=duplicate_chunk_id,
        ),
        _search_result(
            text="Unique semantic search result.",
            score=0.88,
            chunk_id=str(uuid4()),
        ),
    ]
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository(search_results=search_results)
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(query="nil disclosure", organization_id=uuid4())
    )

    assert [result.text for result in response.results] == [
        "First duplicate from semantic search.",
        "Unique semantic search result.",
    ]
    assert response.results[0].score == 0.91
    assert response.results[0].metadata["ranking_strategy"] == "semantic"


@pytest.mark.asyncio
async def test_search_builds_private_conversation_file_filter() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    conversation_id = uuid4()

    await service.search(
        SearchRequest(
            query="contract approval",
            organization_id=uuid4(),
            source_types=["conversation_file"],
            conversation_id=conversation_id,
        )
    )

    assert vector_repo.requests[0]["metadata_filters"] == [
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "visibility_policy": {"scope": "conversation"},
        }
    ]


@pytest.mark.asyncio
async def test_search_builds_file_narrowed_private_filters() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    conversation_id = uuid4()
    file_a = uuid4()
    file_b = uuid4()

    await service.search(
        SearchRequest(
            query="contract approval",
            organization_id=uuid4(),
            source_types=["conversation_file"],
            conversation_id=conversation_id,
            file_ids=[file_a, file_b],
        )
    )

    assert vector_repo.requests[0]["metadata_filters"] == [
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "conversation_file_id": str(file_a),
            "visibility_policy": {"scope": "conversation"},
        },
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "conversation_file_id": str(file_b),
            "visibility_policy": {"scope": "conversation"},
        },
    ]


@pytest.mark.asyncio
async def test_search_builds_combined_shared_and_private_filters() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    conversation_id = uuid4()

    await service.search(
        SearchRequest(
            query="nil contract approval",
            organization_id=uuid4(),
            source_types=["admin_upload", "conversation_file"],
            conversation_id=conversation_id,
            visibility_context={"role": "athlete"},
        )
    )

    assert vector_repo.requests[0]["metadata_filters"] == [
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


@pytest.mark.asyncio
async def test_search_uses_hybrid_repository_when_strategy_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "hybrid")
    monkeypatch.setattr(
        "app.services.search_service.settings.KB_HYBRID_CANDIDATE_LIMIT",
        25,
    )
    monkeypatch.setattr("app.services.search_service.settings.KB_RRF_K", 42)
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    organization_id = uuid4()

    response = await service.search(
        SearchRequest(
            query="nil disclosure",
            organization_id=organization_id,
            visibility_context={"role": "athlete"},
        )
    )

    assert response.total == 3
    assert response.results[0].metadata["ranking_strategy"] == "hybrid"
    assert vector_repo.requests == []
    assert vector_repo.hybrid_requests[0]["max_docs"] == 25
    assert vector_repo.hybrid_requests[0]["final_limit"] == 10
    assert vector_repo.hybrid_requests[0]["rrf_k"] == 42
    assert vector_repo.hybrid_requests[0]["metadata_filters"] == [
        {
            "source_type": "admin_upload",
            "visibility_policy": {"scope": "all_athletes"},
        }
    ]


@pytest.mark.asyncio
async def test_hybrid_search_sends_acronym_keyword_query_to_lexical_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "hybrid")
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )

    await service.search(
        SearchRequest(query="NIL disclosure", organization_id=uuid4())
    )

    assert vector_repo.hybrid_requests[0]["query_text"] == "NIL disclosure"


@pytest.mark.asyncio
async def test_semantic_search_handles_paraphrase_query_without_reranker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_RERANK_ENABLED", True)
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository(
        search_results=[
            _search_result(
                text="NIL policy applies to money earned from name, image, and likeness.",
                score=0.86,
                chunk_id=str(uuid4()),
            )
        ]
    )
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    rerank_provider = FakeRerankProvider(scores=[0.99])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
        rerank_provider=rerank_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(
            query="Can I get paid for using my personal brand?",
            organization_id=uuid4(),
        )
    )

    assert response.results[0].metadata["ranking_strategy"] == "semantic"
    assert vector_repo.requests[0]["query_vector"] == [0.1, 0.2, 0.3]
    assert vector_repo.hybrid_requests == []
    assert rerank_provider.requests == []


@pytest.mark.asyncio
async def test_search_reranks_hybrid_candidates_before_applying_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "hybrid")
    monkeypatch.setattr("app.services.search_service.settings.KB_RERANK_ENABLED", True)
    monkeypatch.setattr(
        "app.services.search_service.settings.KB_RERANK_CANDIDATE_LIMIT",
        50,
    )
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    rerank_provider = FakeRerankProvider(
        reranked_indexes=[1, 0, 2],
        scores=[0.98, 0.72, 0.51],
    )
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
        rerank_provider=rerank_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(
            query="nil disclosure",
            organization_id=uuid4(),
            limit=2,
            visibility_context={"role": "athlete"},
        )
    )

    assert [result.text for result in response.results] == [
        "Hybrid second result",
        "Hybrid first result",
    ]
    assert response.results[0].score == 0.98
    assert response.results[0].metadata["rerank_score"] == 0.98
    assert response.results[0].metadata["hybrid_score"] == 0.04
    assert response.results[0].metadata["ranking_strategy"] == "hybrid_rerank"
    assert response.results[1].score == 0.72
    assert vector_repo.hybrid_requests[0]["final_limit"] == 50
    assert rerank_provider.requests[0]["query"] == "nil disclosure"
    assert rerank_provider.requests[0]["top_n"] == 2
    assert [
        candidate.original_index
        for candidate in rerank_provider.requests[0]["candidates"]
    ] == [0, 1, 2]


@pytest.mark.asyncio
async def test_search_sends_only_unique_hybrid_candidates_to_reranker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "hybrid")
    monkeypatch.setattr("app.services.search_service.settings.KB_RERANK_ENABLED", True)
    duplicate_chunk_id = uuid4()
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository(
        hybrid_results=[
            _hybrid_result(
                text="First hybrid duplicate.",
                hybrid_score=0.05,
                semantic_rank=1,
                lexical_rank=1,
                chunk_id=duplicate_chunk_id,
            ),
            _hybrid_result(
                text="Later hybrid duplicate.",
                hybrid_score=0.04,
                semantic_rank=2,
                lexical_rank=2,
                chunk_id=duplicate_chunk_id,
            ),
            _hybrid_result(
                text="Unique hybrid candidate.",
                hybrid_score=0.03,
                semantic_rank=3,
                lexical_rank=None,
            ),
        ]
    )
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    rerank_provider = FakeRerankProvider(scores=[0.9, 0.8])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
        rerank_provider=rerank_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(query="nil disclosure", organization_id=uuid4())
    )

    candidates = rerank_provider.requests[0]["candidates"]
    assert [candidate.text for candidate in candidates] == [
        "First hybrid duplicate.",
        "Unique hybrid candidate.",
    ]
    assert [result.text for result in response.results] == [
        "First hybrid duplicate.",
        "Unique hybrid candidate.",
    ]


@pytest.mark.asyncio
async def test_search_keeps_hybrid_order_when_reranker_fails_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "hybrid")
    monkeypatch.setattr("app.services.search_service.settings.KB_RERANK_ENABLED", True)
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    rerank_provider = FakeRerankProvider(scores=[None, None, None])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
        rerank_provider=rerank_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(
            query="nil disclosure",
            organization_id=uuid4(),
            limit=2,
            visibility_context={"role": "athlete"},
        )
    )

    assert [result.text for result in response.results] == [
        "Hybrid first result",
        "Hybrid second result",
    ]
    assert response.results[0].score == 0.05
    assert response.results[0].metadata["rerank_score"] is None
    assert response.results[0].metadata["ranking_strategy"] == "hybrid"
    assert response.results[1].score == 0.04


@pytest.mark.asyncio
async def test_semantic_search_does_not_call_reranker_when_rerank_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "semantic")
    monkeypatch.setattr("app.services.search_service.settings.KB_RERANK_ENABLED", True)
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    rerank_provider = FakeRerankProvider(scores=[0.9])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
        rerank_provider=rerank_provider,  # type: ignore[arg-type]
    )

    await service.search(
        SearchRequest(
            query="nil disclosure",
            organization_id=uuid4(),
            visibility_context={"role": "athlete"},
        )
    )

    assert vector_repo.hybrid_requests == []
    assert vector_repo.requests
    assert rerank_provider.requests == []


@pytest.mark.asyncio
async def test_search_falls_back_to_semantic_when_hybrid_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "hybrid")
    config_service = FakeConfigurationService()
    duplicate_chunk_id = str(uuid4())
    vector_repo = FakeVectorRepository(
        fail_hybrid=True,
        search_results=[
            _search_result(
                text="First fallback duplicate.",
                score=0.91,
                chunk_id=duplicate_chunk_id,
            ),
            _search_result(
                text="Later fallback duplicate.",
                score=0.99,
                chunk_id=duplicate_chunk_id,
            ),
            _search_result(
                text="Unique fallback result.",
                score=0.88,
                chunk_id=str(uuid4()),
            ),
        ],
    )
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(
            query="contract approval",
            organization_id=uuid4(),
            source_types=["conversation_file"],
            conversation_id=uuid4(),
        )
    )

    assert [result.text for result in response.results] == [
        "First fallback duplicate.",
        "Unique fallback result.",
    ]
    assert len(vector_repo.hybrid_requests) == 1
    assert len(vector_repo.requests) == 1
    assert vector_repo.requests[0]["metadata_filters"] == (
        vector_repo.hybrid_requests[0]["metadata_filters"]
    )


@pytest.mark.asyncio
async def test_search_logs_safe_hybrid_rerank_metadata_without_raw_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.search_service.settings.KB_SEARCH_STRATEGY", "hybrid")
    monkeypatch.setattr("app.services.search_service.settings.KB_RERANK_ENABLED", True)
    monkeypatch.setattr(
        "app.services.search_service.settings.LITELLM_EMBED_MODEL",
        "playbook-embed",
    )
    monkeypatch.setattr(
        "app.services.search_service.settings.LITELLM_RERANK_MODEL",
        "playbook-rerank",
    )
    fake_logger = FakeLogger()
    monkeypatch.setattr("app.services.search_service.logger", fake_logger)
    sensitive_query = "Can I sign this private NIL contract?"
    sensitive_text = "source_uri=https://storage.test/private.pdf?signature=secret"
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository(
        hybrid_results=[
            _hybrid_result(
                text=sensitive_text,
                hybrid_score=0.05,
                semantic_rank=1,
                lexical_rank=1,
            )
        ]
    )
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    rerank_provider = FakeRerankProvider(scores=[0.91])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
        rerank_provider=rerank_provider,  # type: ignore[arg-type]
    )

    await service.search(SearchRequest(query=sensitive_query, organization_id=uuid4()))

    rendered_logs = repr(fake_logger.events)
    assert sensitive_query not in rendered_logs
    assert sensitive_text not in rendered_logs
    assert "signature=secret" not in rendered_logs
    assert "query_sha256" in rendered_logs
    assert "embed_model" in rendered_logs
    assert "playbook-embed" in rendered_logs
    assert "rerank_model" in rendered_logs
    assert "playbook-rerank" in rendered_logs
    assert "candidate_count" in rendered_logs
    assert "score_summary" in rendered_logs
    assert "ranking_strategy_counts" in rendered_logs
