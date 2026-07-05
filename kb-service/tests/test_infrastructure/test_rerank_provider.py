from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.infrastructure.llm import builder
from app.infrastructure.rerankers.base import RerankCandidate, RerankProviderError
from app.infrastructure.rerankers.litellm import LiteLLMRerankProvider


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: object | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self) -> object:
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _FakeClient:
    def __init__(
        self,
        response: _FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or _FakeResponse(200, {"results": []})
        self.error = error
        self.requests: list[dict[str, object]] = []

    def post(self, path: str, *, json: dict[str, object]) -> _FakeResponse:
        self.requests.append({"path": path, "json": json})
        if self.error is not None:
            raise self.error
        return self.response


def _candidates() -> list[RerankCandidate]:
    return [
        RerankCandidate(original_index=10, chunk_id=uuid4(), text="alpha policy"),
        RerankCandidate(original_index=11, chunk_id=uuid4(), text="beta policy"),
        RerankCandidate(original_index=12, chunk_id=uuid4(), text="gamma policy"),
    ]


def test_litellm_rerank_maps_request_and_response_by_document_index() -> None:
    candidates = _candidates()
    client = _FakeClient(
        _FakeResponse(
            200,
            {
                "results": [
                    {"index": 2, "relevance_score": 0.96, "document": "ignored"},
                    {"index": 0, "relevance_score": 0.73, "document": "ignored"},
                ]
            },
        )
    )
    provider = LiteLLMRerankProvider(
        client=client,
        model_name="playbook-rerank",
        fail_open=True,
    )

    results = provider.rerank(
        query="Which policy applies?",
        candidates=candidates,
        top_n=2,
    )

    assert client.requests == [
        {
            "path": "/rerank",
            "json": {
                "model": "playbook-rerank",
                "query": "Which policy applies?",
                "documents": ["alpha policy", "beta policy", "gamma policy"],
                "top_n": 2,
            },
        }
    ]
    assert [item.candidate.chunk_id for item in results] == [
        candidates[2].chunk_id,
        candidates[0].chunk_id,
    ]
    assert [item.candidate.original_index for item in results] == [12, 10]
    assert [item.rerank_score for item in results] == [0.96, 0.73]
    assert [item.rank for item in results] == [1, 2]


def test_litellm_rerank_clamps_top_n_to_candidate_count() -> None:
    candidates = _candidates()
    client = _FakeClient(
        _FakeResponse(
            200,
            {"results": [{"index": 0, "relevance_score": 0.8}]},
        )
    )
    provider = LiteLLMRerankProvider(
        client=client,
        model_name="playbook-rerank",
        fail_open=True,
    )

    provider.rerank(query="query", candidates=candidates, top_n=50)

    assert client.requests[0]["json"]["top_n"] == len(candidates)  # type: ignore[index]


def test_litellm_rerank_empty_candidates_skip_http() -> None:
    client = _FakeClient()
    provider = LiteLLMRerankProvider(
        client=client,
        model_name="playbook-rerank",
        fail_open=True,
    )

    assert provider.rerank(query="query", candidates=[]) == []
    assert client.requests == []


@pytest.mark.parametrize(
    "error_or_response",
    [
        httpx.TimeoutException("timed out"),
        httpx.TransportError("connection failed"),
        _FakeResponse(503, {"error": "unavailable"}),
    ],
)
def test_litellm_rerank_fail_open_returns_input_order_on_retryable_failures(
    error_or_response: Exception | _FakeResponse,
) -> None:
    candidates = _candidates()
    client = (
        _FakeClient(error=error_or_response)
        if isinstance(error_or_response, Exception)
        else _FakeClient(response=error_or_response)
    )
    provider = LiteLLMRerankProvider(
        client=client,
        model_name="playbook-rerank",
        fail_open=True,
    )

    results = provider.rerank(query="query", candidates=candidates, top_n=2)

    assert [item.candidate.chunk_id for item in results] == [
        candidate.chunk_id for candidate in candidates
    ]
    assert [item.rerank_score for item in results] == [None, None, None]
    assert [item.rank for item in results] == [1, 2, 3]


@pytest.mark.parametrize(
    "error_or_response",
    [
        httpx.TimeoutException("timed out"),
        httpx.TransportError("connection failed"),
        _FakeResponse(503, {"error": "unavailable"}),
    ],
)
def test_litellm_rerank_fail_closed_raises_on_retryable_failures(
    error_or_response: Exception | _FakeResponse,
) -> None:
    client = (
        _FakeClient(error=error_or_response)
        if isinstance(error_or_response, Exception)
        else _FakeClient(response=error_or_response)
    )
    provider = LiteLLMRerankProvider(
        client=client,
        model_name="playbook-rerank",
        fail_open=False,
    )

    with pytest.raises(RerankProviderError):
        provider.rerank(query="query", candidates=_candidates())


@pytest.mark.parametrize(
    "response",
    [
        _FakeResponse(400, {"error": "bad request"}),
        _FakeResponse(200, {"items": []}),
        _FakeResponse(200, {"results": [{"index": 99, "relevance_score": 0.1}]}),
        _FakeResponse(200, {"results": [{"index": 0}]}),
        _FakeResponse(200, json_error=ValueError("not json")),
    ],
)
def test_litellm_rerank_malformed_or_nonretryable_responses_raise(
    response: _FakeResponse,
) -> None:
    provider = LiteLLMRerankProvider(
        client=_FakeClient(response=response),
        model_name="playbook-rerank",
        fail_open=True,
    )

    with pytest.raises(RerankProviderError):
        provider.rerank(query="query", candidates=_candidates())


def test_litellm_rerank_logs_metadata_without_raw_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeLogger:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict[str, object]]] = []

        def info(self, event: str, **kwargs: object) -> None:
            self.events.append((event, kwargs))

        def warning(self, event: str, **kwargs: object) -> None:
            self.events.append((event, kwargs))

    fake_logger = _FakeLogger()
    monkeypatch.setattr("app.infrastructure.rerankers.litellm.logger", fake_logger)
    sensitive_query = "Can I sign this private NIL contract?"
    sensitive_text = "source_uri=https://storage.test/private.pdf?signature=secret"
    provider = LiteLLMRerankProvider(
        client=_FakeClient(
            _FakeResponse(
                200,
                {"results": [{"index": 0, "relevance_score": 0.7}]},
            )
        ),
        model_name="playbook-rerank",
        fail_open=True,
    )

    provider.rerank(
        query=sensitive_query,
        candidates=[RerankCandidate(original_index=0, chunk_id=uuid4(), text=sensitive_text)],
    )

    rendered_logs = repr(fake_logger.events)
    assert sensitive_query not in rendered_logs
    assert sensitive_text not in rendered_logs
    assert "signature=secret" not in rendered_logs
    assert "candidate_count" in rendered_logs
    assert "total_chars" in rendered_logs


def test_litellm_rerank_client_builder_caches_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_clients: list[SimpleNamespace] = []

    def fake_client(**kwargs: object) -> SimpleNamespace:
        client = SimpleNamespace(kwargs=kwargs, closed=False)

        def close() -> None:
            client.closed = True

        client.close = close
        created_clients.append(client)
        return client

    builder.close_litellm_rerank_client()
    monkeypatch.setattr(builder.settings, "LITELLM_BASE_URL", "http://litellm:4000")
    monkeypatch.setattr(builder.settings, "LITELLM_API_KEY", "litellm-key")
    monkeypatch.setattr(builder.settings, "KB_RERANK_TIMEOUT_SECONDS", 2.5)
    monkeypatch.setattr(builder.httpx, "Client", fake_client)

    first = builder.get_litellm_rerank_client()
    second = builder.get_litellm_rerank_client()

    assert first is second
    assert len(created_clients) == 1
    assert created_clients[0].kwargs["base_url"] == "http://litellm:4000"
    assert created_clients[0].kwargs["headers"] == {
        "Authorization": "Bearer litellm-key"
    }

    builder.close_litellm_rerank_client()
    assert created_clients[0].closed is True
