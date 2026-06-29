"""LangGraph topology for admin analytics chat generation."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.runtime_context import AdminChatRuntimeContext
from app.agents.states.admin_chat_state import AdminChatState


def create_admin_chat_graph(nodes: dict[str, object]) -> StateGraph:
    """Create the admin chat graph topology without compiling it."""
    builder = StateGraph(AdminChatState, context_schema=AdminChatRuntimeContext)
    for name, node_fn in nodes.items():
        builder.add_node(name, node_fn)

    builder.add_edge(START, "load_session")
    builder.add_edge("load_session", "build_context")
    builder.add_edge("build_context", "scope_check")
    builder.add_conditional_edges(
        "scope_check",
        _route_after_scope_check,
        {
            "run_agent": "run_agent",
            "save_response": "save_response",
        },
    )
    builder.add_edge("run_agent", "save_response")
    builder.add_edge("save_response", END)
    return builder


def _route_after_scope_check(state: AdminChatState) -> str:
    if bool(state.get("should_bypass_agent", False)):
        return "save_response"
    return "run_agent"
