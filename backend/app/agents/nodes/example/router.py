"""Deterministic routing for the example graph.

Pattern: a router is a pure function over state that returns the name of the
next node. The factory takes a ``{decision -> node_name}`` mapping so topology
stays declarative and the router validates the decision before dispatching.
"""

from collections.abc import Callable

import structlog

from app.agents.states.example_state import ExampleState

logger = structlog.get_logger(__name__)


def create_router_node(node_mapping: dict[str, str]) -> Callable[[ExampleState], str]:
    """Create a deterministic router from a decision->node mapping.

    Args:
        node_mapping: Maps ``state["decision"]`` values to target node names.

    Returns:
        A router function returning the target node name.
    """

    def router(state: ExampleState) -> str:
        """Route to the target node based on ``state["decision"]``.

        Raises:
            ValueError: If the decision is empty or unknown.
        """
        decision = state.get("decision")
        example_id = state.get("example_id")

        if not decision:
            logger.error("routing_failed_empty_decision", example_id=str(example_id) if example_id else None)
            raise ValueError("state.decision cannot be empty")

        if decision not in node_mapping:
            valid_options = list(node_mapping.keys())
            logger.error(
                "routing_failed_unknown_decision",
                example_id=str(example_id) if example_id else None,
                decision=decision,
                valid_options=valid_options,
            )
            raise ValueError(f"Unknown decision: {decision}. Valid options: {valid_options}")

        target_node = node_mapping[decision]
        logger.info(
            "routing_to_node",
            example_id=str(example_id) if example_id else None,
            decision=decision,
            target_node=target_node,
        )
        return target_node

    return router
