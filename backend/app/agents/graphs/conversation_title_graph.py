"""LangGraph topology for conversation title generation."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.runtime_context import ConversationTitleRuntimeContext
from app.agents.states.conversation_title_state import ConversationTitleState


def create_conversation_title_graph(nodes: dict[str, object]) -> StateGraph:
    """Create the conversation title graph topology without compiling it."""
    builder = StateGraph(
        ConversationTitleState,
        context_schema=ConversationTitleRuntimeContext,
    )
    for name, node_fn in nodes.items():
        builder.add_node(name, node_fn)

    builder.add_edge(START, "load_title_context")
    builder.add_edge("load_title_context", "generate_title")
    builder.add_edge("generate_title", "save_title")
    builder.add_edge("save_title", END)
    return builder
