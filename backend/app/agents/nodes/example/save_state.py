"""save_state node - persist generated state back to the database.

Pattern: the terminal node before END writes the chain's output to persistence
and returns an empty dict (it has side effects only). This generic version
persists the result's title onto the ``Example`` entity's ``name`` to show the
write path; replace with your domain's persistence logic.
"""

from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.states.example_state import ExampleState
from app.core.exceptions import DatabaseError
from app.repositories.example_repository import ExampleRepository

logger = structlog.get_logger(__name__)


def create_save_state_node(
    get_session: Callable[[], AsyncGenerator[AsyncSession, Any]],
) -> Callable[[Any], Any]:
    """Create the save_state node bound to a session factory."""

    async def save_state_node(state: ExampleState) -> dict:
        """Persist the generated result to the database.

        Returns an empty dict (side-effect-only node).

        Raises:
            DatabaseError: If the database write fails (retryable).
        """
        example_id = state["example_id"]
        result = state.get("result")
        saved: list[str] = []

        try:
            async for session in get_session():
                repo = ExampleRepository(session)
                logger.info("saving_state", example_id=str(example_id))

                if result is not None:
                    await repo.update(example_id, {"name": result.title})
                    saved.append("result")
                break  # only the first yielded session
        except Exception as e:
            logger.error(
                "save_state_failed",
                example_id=str(example_id),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise DatabaseError(
                message=f"Failed to save state to database: {str(e)}",
                retryable=True,
                details={"example_id": str(example_id), "error_type": type(e).__name__},
            ) from e
        else:
            logger.info("state_saved", example_id=str(example_id), saved=saved)
            return {}

    return save_state_node
