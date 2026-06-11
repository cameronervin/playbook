"""Chain-execution nodes for the example workflow.

Pattern: a chain node wraps a chain with operational concerns the chain itself
should not know about - timeouts, structured-error conversion, and (optionally)
bounded repair retries. Nodes are async so LLM calls never block the event loop.

``create_example_nodes`` returns a dict of node-name -> node-fn, including the
load_state and save_state nodes, ready for the graph to register.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.messages import AIMessage

from app.agents.nodes.example.load_state import create_load_state_node
from app.agents.nodes.example.save_state import create_save_state_node
from app.agents.states.example_state import ExampleState
from app.core.config import Settings
from app.core.exceptions import LLMError, LLMTimeoutError

logger = structlog.get_logger(__name__)

# Message shown to the user after the chain completes its work.
EXAMPLE_DONE_MESSAGE = "I've generated your result - take a look on the right!"


def create_example_nodes(
    *,
    chains: dict[str, Any],
    get_session: Callable,
    settings: Settings,
) -> dict[str, Callable]:
    """Create example-workflow nodes with chain + infrastructure wiring.

    Args:
        chains: Chain instances keyed by chain name.
        get_session: Async session-factory dependency for load/save nodes.

    Returns:
        Dict of node functions keyed by node name.
    """

    async def _execute_chain_with_timeout(
        chain_name: str, chain: Any, state: ExampleState, timeout: int
    ) -> Any:
        """Run a chain with a timeout, converting failures to AppError types."""
        try:
            async with asyncio.timeout(timeout):
                return await chain.ainvoke(state)
        except TimeoutError as te:
            logger.exception(
                "chain_timeout",
                chain=chain_name,
                example_id=str(state.get("example_id")),
                timeout_seconds=timeout,
            )
            raise LLMTimeoutError(
                message=f"{chain_name} execution timed out after {timeout} seconds",
                details={"chain": chain_name, "example_id": str(state.get("example_id"))},
            ) from te
        except Exception as e:
            logger.error(
                "chain_failed",
                chain=chain_name,
                example_id=str(state.get("example_id")),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise LLMError(
                message=f"{chain_name} execution failed: {str(e)}",
                details={"chain": chain_name, "example_id": str(state.get("example_id"))},
            ) from e

    async def example_node(state: ExampleState) -> dict:
        """Run the example chain and return the structured result + a message."""
        result = await _execute_chain_with_timeout(
            "example", chains["example"], state, settings.LLM_TIMEOUT
        )
        return {
            "result": result["structured_response"],
            "messages": [AIMessage(content=EXAMPLE_DONE_MESSAGE)],
        }

    return {
        "example_node": example_node,
        "load_state": create_load_state_node(get_session),
        "save_state": create_save_state_node(get_session),
    }
