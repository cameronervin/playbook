"""load_state node - placeholder state hydration for the scaffold graph.

The Playbook product schema replaced the scaffold Example repository. Keep this
node importable until a Playbook-specific graph replaces the example workflow.
"""

from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.states.example_state import ExampleState

logger = structlog.get_logger(__name__)


def create_load_state_node(
    get_session: Callable[[], AsyncGenerator[AsyncSession, Any]],
) -> Callable[[Any], Any]:
    """Create the load_state node bound to a session factory.

    Args:
        get_session: Async generator dependency that yields an AsyncSession.

    Returns:
        An async LangGraph node function.
    """

    async def load_state_node(state: ExampleState) -> dict:
        """Load existing data for this entity into state.

        Returns a partial dict with only the fields hydrated from the DB.

        The scaffold Example repository was removed with the Playbook schema.
        Returning no updates keeps the graph shape importable without touching
        product data.
        """
        example_id = state["example_id"]
        logger.info("example_state_load_skipped", example_id=str(example_id))
        return {}

    return load_state_node
