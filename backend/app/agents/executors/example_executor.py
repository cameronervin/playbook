"""Executor for the example workflow.

Pattern: the executor is the seam between the API layer and the graph. It builds
the initial state and the ainvoke config (thread id, tracing, recursion limit),
then drives ``graph.ainvoke(...)``. Routes call ``execute()``; they never touch
the graph directly. Retries are handled at the node level.

main.py constructs this as ``ExampleExecutor(compiled_graph, tracing_enabled=...)``
and stores it on ``app.state.example_executor``; ``get_example_executor`` is the
FastAPI dependency that retrieves it.
"""

from typing import Any
from uuid import UUID

import structlog
from fastapi import Request
from langchain_core.messages import BaseMessage

from app.agents.retry import RetryHandler
from app.observability.agent_trace import build_graph_invoke_config

logger = structlog.get_logger(__name__)

EXAMPLE_MODE = "example"


def get_example_executor(request: Request) -> "ExampleExecutor":
    """FastAPI dependency: return the example executor from app state."""
    return request.app.state.example_executor


class ExampleExecutor:
    """Runs the compiled example graph for a given entity."""

    def __init__(
        self,
        compiled_graph: Any,
        retry_handler: RetryHandler | None = None,
        tracing_enabled: bool = False,
    ):
        """Initialize the executor.

        Args:
            compiled_graph: The compiled LangGraph instance.
            retry_handler: Optional retry handler (created with defaults if None).
            tracing_enabled: Whether to attach tracing callbacks at invoke time.
        """
        self.graph = compiled_graph
        self.retry = retry_handler or RetryHandler()
        self.tracing_enabled = tracing_enabled

    async def execute(
        self,
        example_id: UUID,
        phase: str,
        messages: list[BaseMessage],
        configuration_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute the graph for a given phase.

        Args:
            example_id: Entity id; also used as the checkpointer thread id.
            phase: The routing decision (e.g. ``"example"``).
            messages: Conversation messages seeding the run.
            configuration_id: Optional KB pipeline id threaded into configurable.

        Returns:
            The final graph state dict.
        """
        state_input = {
            "example_id": example_id,
            "decision": phase,
            "messages": messages,
        }

        extra_configurable: dict[str, Any] = {}
        if configuration_id:
            extra_configurable["kb_configuration_id"] = configuration_id

        config = build_graph_invoke_config(
            thread_id=example_id,
            phase=phase,
            mode=EXAMPLE_MODE,
            extra_configurable=extra_configurable,
        )

        logger.info(
            "executing_graph",
            example_id=str(example_id),
            phase=phase,
            message_count=len(messages),
            tracing_enabled=self.tracing_enabled,
            recursion_limit=config.get("recursion_limit"),
        )

        try:
            result = await self.graph.ainvoke(state_input, config)
        except Exception as graph_error:
            logger.error(
                "graph_execution_failed",
                example_id=str(example_id),
                phase=phase,
                error=str(graph_error),
                error_type=type(graph_error).__name__,
                exc_info=True,
            )
            raise
        else:
            logger.info("graph_execution_completed", example_id=str(example_id), phase=phase)
            return result
