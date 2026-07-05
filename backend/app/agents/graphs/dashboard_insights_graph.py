"""LangGraph topology for dashboard insight generation."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.runtime_context import DashboardInsightsRuntimeContext
from app.agents.states.dashboard_insights_state import DashboardInsightsState


def create_dashboard_insights_graph(nodes: dict[str, object]) -> StateGraph:
    """Create the dashboard insights graph topology without compiling it."""
    builder = StateGraph(
        DashboardInsightsState,
        context_schema=DashboardInsightsRuntimeContext,
    )
    for name, node_fn in nodes.items():
        builder.add_node(name, node_fn)

    builder.add_edge(START, "load_run")
    builder.add_edge("load_run", "build_snapshot")
    builder.add_edge("build_snapshot", "generate_insights")
    builder.add_edge("generate_insights", "save_output")
    builder.add_edge("save_output", END)
    return builder
