from __future__ import annotations

import sys
import types

import pytest

from app.core.config import Settings, set_settings_override
from evals.core import graph_env


def _settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "not-the-default-secret",
        "LLM_PROVIDER_MODE": "litellm",
        "LLM_CHAT_MODEL": "playbook-chat",
        "LITELLM_BASE_URL": "http://litellm.test:4000",
        "LITELLM_API_KEY": "backend-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def _clear_graph_env_caches() -> None:
    graph_env.get_eval_chat_model.cache_clear()
    graph_env.get_eval_embeddings.cache_clear()
    yield
    graph_env.get_eval_chat_model.cache_clear()
    graph_env.get_eval_embeddings.cache_clear()
    set_settings_override(None)


def test_eval_models_use_eval_litellm_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_calls: list[dict[str, object]] = []
    embedding_calls: list[dict[str, object]] = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            chat_calls.append(kwargs)

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs: object) -> None:
            embedding_calls.append(kwargs)

    fake_langchain_openai = types.SimpleNamespace(
        ChatOpenAI=FakeChatOpenAI,
        OpenAIEmbeddings=FakeOpenAIEmbeddings,
    )
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_langchain_openai)
    set_settings_override(
        _settings(
            EVAL_LITELLM_API_KEY="eval-key",
            EVAL_EMBEDDINGS_MODEL="playbook-embed",
        )
    )

    graph_env.get_eval_chat_model()
    graph_env.get_eval_embeddings()

    assert chat_calls[0]["api_key"] == "eval-key"
    assert chat_calls[0]["model"] == "playbook-chat"
    assert embedding_calls[0]["api_key"] == "eval-key"
    assert embedding_calls[0]["model"] == "playbook-embed"


def test_eval_models_require_eval_litellm_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            raise AssertionError("ChatOpenAI should not be constructed")

    fake_langchain_openai = types.SimpleNamespace(ChatOpenAI=FakeChatOpenAI)
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_langchain_openai)
    set_settings_override(_settings(EVAL_LITELLM_API_KEY=""))

    with pytest.raises(RuntimeError, match="EVAL_LITELLM_API_KEY is required"):
        graph_env.get_eval_chat_model()


def test_eval_models_reject_backend_litellm_key_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            raise AssertionError("ChatOpenAI should not be constructed")

    fake_langchain_openai = types.SimpleNamespace(ChatOpenAI=FakeChatOpenAI)
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_langchain_openai)
    set_settings_override(_settings(EVAL_LITELLM_API_KEY="backend-key"))

    with pytest.raises(RuntimeError, match="must be distinct"):
        graph_env.get_eval_chat_model()
