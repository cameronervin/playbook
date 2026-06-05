"""Bridge between the agent-agnostic eval core and the project's agent layer.

This is the ONLY module under ``evals`` that imports ``app.*``. It provides:

- ``get_eval_chat_model()`` / ``get_eval_embeddings()`` — the evaluator (judge)
  LLM and embeddings, both routed through the same LiteLLM proxy the app uses,
  so every evaluator model is LiteLLM-provisioned regardless of LLM_PROVIDER_MODE.
- ``get_example_chains()`` — the agent chains under test, built with the project's
  configured provider (whatever the app normally runs with).

Chain-level adapters need no DB session or checkpointer; the underlying chains
are not DB-coupled (the full graphs are). All ``app.*`` and ``langchain_openai``
imports are lazy (inside the functions) so importing this module never forces
provider init and ``compileall`` succeeds without the heavy deps installed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseChatModel


# --------------------------------------------------------------------------- #
# Evaluator models — pinned to LiteLLM (OpenAI-compatible).
# --------------------------------------------------------------------------- #
@lru_cache
def get_eval_chat_model() -> "BaseChatModel":
    """Judge LLM, routed through LiteLLM."""
    from langchain_openai import ChatOpenAI

    from app.core.config import settings

    return ChatOpenAI(
        model=settings.EVAL_JUDGE_MODEL or settings.LLM_CHAT_MODEL,
        base_url=settings.LITELLM_BASE_URL,
        api_key=settings.LITELLM_API_KEY or "x",
        temperature=0,
        timeout=settings.LLM_TIMEOUT,
    )


@lru_cache
def get_eval_embeddings() -> "Embeddings | None":
    """Ragas embeddings (answer_relevancy), routed through LiteLLM.

    Returns ``None`` when ``EVAL_EMBEDDINGS_MODEL`` is blank or construction fails,
    in which case the embeddings-dependent metric is skipped rather than erroring.
    """
    from app.core.config import settings

    model = settings.EVAL_EMBEDDINGS_MODEL
    if not model:
        return None
    try:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=model,
            base_url=settings.LITELLM_BASE_URL,
            api_key=settings.LITELLM_API_KEY or "x",
        )
    except Exception:  # noqa: BLE001 — embeddings optional; skip the metric instead
        return None


# --------------------------------------------------------------------------- #
# Agent chains under test — built with the project's configured provider.
# --------------------------------------------------------------------------- #
def _agent_chat_model() -> "BaseChatModel":
    # Imported lazily so importing this module never forces provider init.
    from app.infrastructure.llm.factory import get_llm_provider

    return get_llm_provider().get_chat_model()


@lru_cache
def get_example_chains() -> dict[str, Any]:
    """Example chain set: ``{"example": chain}``."""
    from app.agents.builders.chains_builder import create_example_chain_set

    return create_example_chain_set(_agent_chat_model())
