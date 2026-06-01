"""load_state node - hydrate graph state from persistence.

Pattern: the first node in the graph reads any existing data for this entity
out of the database and returns a *partial* state update. Returning only the
keys it loaded keeps reducers happy and lets later nodes skip completed work.

This generic version loads the ``Example`` entity into ``loaded_context``;
replace the repository call with your domain's hydration logic.
"""

from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.states.example_state import ExampleState
from app.core.exceptions import DatabaseError
from app.repositories.example_repository import ExampleRepository

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

        Raises:
            DatabaseError: If the database read fails (retryable).
        """
        example_id = state["example_id"]
        updates: dict = {}

        try:
            async for session in get_session():
                repo = ExampleRepository(session)
                logger.info("loading_state", example_id=str(example_id))

                entity = await repo.get(example_id)
                if entity is not None:
                    updates["loaded_context"] = {
                        "id": str(entity.id),
                        "name": entity.name,
                        "status": entity.status,
                    }
                break  # only the first yielded session
        except Exception as e:
            logger.exception(
                "load_state_failed",
                example_id=str(example_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseError(
                message=f"Failed to load state from database: {str(e)}",
                retryable=True,
                details={"example_id": str(example_id), "error_type": type(e).__name__},
            ) from e
        else:
            logger.info(
                "state_loaded",
                example_id=str(example_id),
                loaded_keys=list(updates.keys()),
            )
            return updates

    return load_state_node
