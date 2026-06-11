"""Generic knowledge-base retrieval tool for the example workflow.

Pattern: a tool is a factory returning a LangChain ``BaseTool``. The tool reads
its target pipeline/collection id from ``config["configurable"]`` at call time,
so retrieval can be scoped per-run without rebuilding the graph. This mirrors a
production multi-tenant KB tool while staying domain-neutral.

The ``ToolSpec`` in ``tool_registry.py`` references ``create_example_kb_tool``
and decides which chains receive it.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.exceptions import KnowledgebaseError
from app.infrastructure.knowledgebase import (
    BaseKnowledgebaseProvider,
    get_kb_provider,
)

logger = structlog.get_logger(__name__)

_NO_RESULTS_MSG = "No relevant knowledge base context found for this query."
_UNAVAILABLE_MSG = "Knowledge base temporarily unavailable."
DEFAULT_MAX_DOCS = 10
DEFAULT_SCORE_THRESHOLD = 0.7


class QueryKnowledgebaseInput(BaseModel):
    """Input schema for the example KB tool."""

    query: str = Field(
        ...,
        description="Natural language query describing the context needed",
    )
    max_docs: int = Field(
        default=DEFAULT_MAX_DOCS,
        ge=1,
        le=50,
        description="Maximum number of chunks to retrieve",
    )
    score_threshold: float = Field(
        default=DEFAULT_SCORE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for results (0.0-1.0)",
    )


def create_example_kb_tool(
    provider: BaseKnowledgebaseProvider | None = None,
    fallback_configuration_id: str | None = None,
    app_settings: Settings | None = None,
):
    """Factory for the generic KB retrieval tool.

    Reads ``kb_configuration_id`` from LangGraph configurable at call time,
    falling back to ``fallback_configuration_id`` (closure-level) when absent.

    Args:
        provider: Optional provider override for tests.
        fallback_configuration_id: Default pipeline id used when configurable is absent.
    """

    settings = app_settings or get_settings()

    @tool("query_example_knowledgebase", args_schema=QueryKnowledgebaseInput)
    async def _kb_tool(
        query: str,
        max_docs: int = DEFAULT_MAX_DOCS,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
        config: Annotated[RunnableConfig, InjectedToolArg] = None,
    ) -> str:
        """Query the knowledge base for supporting context."""
        kb_provider = (
            provider
            if provider is not None
            else get_kb_provider(app_settings=settings)
        )

        runtime_config_id: str | None = None
        if config and isinstance(config.get("configurable"), dict):
            runtime_config_id = config["configurable"].get("kb_configuration_id")
        effective_config_id = runtime_config_id or fallback_configuration_id

        logger.info(
            "kb_tool_request",
            tool="query_example_knowledgebase",
            query=query[:200],
            max_docs=max_docs,
            configuration_id=effective_config_id,
        )

        try:
            result = await kb_provider.search(
                query=query,
                max_docs=max_docs,
                score_threshold=score_threshold,
                configuration_id=effective_config_id,
            )
        except KnowledgebaseError as exc:
            logger.error("kb_tool_error", query=query[:200], error=str(exc), exc_info=True)
            return _UNAVAILABLE_MSG
        except Exception as exc:
            logger.error("kb_tool_unexpected_error", query=query[:200], error=str(exc), exc_info=True)
            return _UNAVAILABLE_MSG

        if result.zero_hit or not result.context:
            logger.info("kb_tool_zero_hit", query=query[:200])
            return _NO_RESULTS_MSG

        logger.info(
            "kb_tool_success",
            query=query[:200],
            result_count=len(result.sources),
            latency_ms=result.latency_ms,
        )
        return result.context

    return _kb_tool
