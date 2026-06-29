from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain.tools import ToolRuntime

from app.agents.runtime_context import AdminChatRuntimeContext
from app.agents.states.admin_chat_state import AdminChatState
from app.agents.tools.admin_chat import (
    ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE,
    create_admin_chat_query_examples_tool,
)


@dataclass(slots=True)
class FakeSnapshot:
    queries: list[dict[str, Any]] = field(default_factory=list)


def _tool_runtime(context: object | None = None) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=context,
        config={},
        stream_writer=lambda _: None,
        tool_call_id=None,
        store=None,
    )


def _runtime_context(snapshot: FakeSnapshot) -> AdminChatRuntimeContext:
    return AdminChatRuntimeContext(
        session=object(),
        settings=object(),
        stream_service=object(),
        analytics_snapshot=snapshot,
    )


@pytest.mark.asyncio
async def test_admin_chat_query_tool_reads_runtime_snapshot() -> None:
    tool = create_admin_chat_query_examples_tool(ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE)
    snapshot = FakeSnapshot(
        queries=[
            {
                "message_id": "message-1",
                "text": "When do I disclose an NIL deal?",
                "topic_labels": ["nil"],
                "risk_labels": ["compliance"],
                "unanswered_reason": None,
            },
            {
                "message_id": "message-2",
                "text": "Can recruiting staff text this prospect?",
                "topic_labels": ["recruiting"],
                "risk_labels": ["recruiting"],
                "unanswered_reason": "unsupported",
            },
        ]
    )

    result = await tool.ainvoke(
        {
            "runtime": _tool_runtime(_runtime_context(snapshot)),
            "topic_label": "nil",
            "limit": 5,
        }
    )

    assert "message-1" in result
    assert "When do I disclose" in result
    assert "message-2" not in result


@pytest.mark.asyncio
async def test_admin_chat_query_tool_requires_runtime_context() -> None:
    tool = create_admin_chat_query_examples_tool(ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE)

    result = await tool.ainvoke({"runtime": _tool_runtime(), "limit": 5})

    assert result == ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE.unavailable_message


def test_admin_chat_state_is_json_safe() -> None:
    state: AdminChatState = {
        "task_id": "task-1",
        "session_id": "session-1",
        "admin_user_id": "admin-1",
        "user_message_id": "user-message-1",
        "assistant_message_id": "assistant-message-1",
        "organization_id": "org-1",
        "question": "What are athletes most confused about?",
        "window_start": "2026-06-01T00:00:00+00:00",
        "window_end": "2026-06-08T00:00:00+00:00",
        "snapshot_context": "Query volume: 2",
        "allowed_references": [
            {"type": "metric", "id": "analytics.summary"},
            {"type": "query", "id": "message-1"},
        ],
    }

    assert "session" not in state
    assert "analytics_snapshot" not in state
