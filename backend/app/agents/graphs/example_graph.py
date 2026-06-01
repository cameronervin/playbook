"""LangGraph topology for the example workflow - pure structure only.

Pattern: this module declares ONLY which nodes exist and how they connect.
Node *creation* is done by the builders, which pass a ready-made ``nodes`` dict
in here. Keeping topology free of construction logic makes the graph shape easy
to read and the nodes easy to test in isolation.

Flow:  START -> load_state -> (router) -> example_node -> save_state -> END
"""

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.example.router import create_router_node
from app.agents.states.example_state import ExampleState


def create_example_graph(nodes: dict) -> StateGraph:
    """Create the example graph topology (uncompiled).

    Args:
        nodes: Node functions keyed by node name. Expected keys:
            ``load_state``, ``save_state``, ``example_node``.

    Returns:
        A ``StateGraph`` builder; the builders module compiles it with a
        checkpointer.
    """
    builder = StateGraph(ExampleState)

    # Router maps a decision -> node name. The example workflow has one decision.
    node_mapping = {"example": "example_node"}
    router = create_router_node(node_mapping)

    for name, node_fn in nodes.items():
        builder.add_node(name, node_fn)

    builder.add_edge(START, "load_state")
    # Router returns the node name directly, so no path_map is needed.
    builder.add_conditional_edges("load_state", router)
    builder.add_edge("example_node", "save_state")
    builder.add_edge("save_state", END)

    return builder
