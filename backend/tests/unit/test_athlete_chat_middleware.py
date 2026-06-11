from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.context.middleware.athlete_chat_middleware import (
    create_athlete_chat_middleware,
)
from app.core.exceptions import ValidationError


class FakeModel:
    pass


def _request(*, messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=FakeModel(),
        messages=messages,
        tools=[],
        state=state or {},
    )


async def _capture_messages(request: ModelRequest) -> list:
    captured: dict[str, list] = {}
    middleware = create_athlete_chat_middleware()

    async def handler(updated_request: ModelRequest):
        captured["messages"] = updated_request.messages
        return "ok"

    await middleware.awrap_model_call(request, handler)
    return captured["messages"]


@pytest.mark.asyncio
async def test_athlete_chat_middleware_filters_blank_messages_and_preserves_tools() -> None:
    tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "search_playbook_knowledgebase",
                "args": {"query": "nil"},
                "id": "tool-call-1",
                "type": "tool_call",
            }
        ],
    )
    tool_result = ToolMessage(content="Source result", tool_call_id="tool-call-1")

    messages = await _capture_messages(
        _request(
            messages=[
                HumanMessage(content="Previous question"),
                AIMessage(content=""),
                HumanMessage(content="   "),
                tool_call,
                tool_result,
            ],
            state={"user_message_content": "Current question"},
        )
    )

    assert [type(message) for message in messages[:-1]] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
    ]
    assert messages[1].tool_calls == tool_call.tool_calls
    assert messages[2].content == "Source result"


@pytest.mark.asyncio
async def test_athlete_chat_middleware_preserves_bounded_history() -> None:
    messages = await _capture_messages(
        _request(
            messages=[
                HumanMessage(content="Earlier NIL question"),
                AIMessage(content="Earlier answer"),
                HumanMessage(content="Current NIL follow-up"),
            ],
            state={"user_message_content": "Current NIL follow-up"},
        )
    )

    assert [message.content for message in messages[:-1]] == [
        "Earlier NIL question",
        "Earlier answer",
        "Current NIL follow-up",
    ]


@pytest.mark.asyncio
async def test_athlete_chat_middleware_appends_runtime_context() -> None:
    messages = await _capture_messages(
        _request(
            messages=[HumanMessage(content="Can I accept this NIL deal?")],
            state={
                "task_id": "task-123",
                "conversation_id": "conversation-123",
                "user_message_content": "Can I accept this NIL deal?",
                "attached_file_ids": ["file-1", "file-2"],
                "requires_kb_support": True,
                "topic_labels": ["nil"],
                "risk_labels": ["compliance"],
            },
        )
    )

    context = messages[-1].content
    assert "## Athlete Chat Runtime Context" in context
    assert "Can I accept this NIL deal?" in context
    assert "Requires KB support: true" in context
    assert "Topic labels: nil" in context
    assert "Risk labels: compliance" in context
    assert "Attached file count: 2" in context
    assert "Attached file IDs: file-1, file-2" in context
    assert "Source result" not in context


@pytest.mark.asyncio
async def test_athlete_chat_middleware_uses_loop_guard() -> None:
    settings = SimpleNamespace(AGENT_MAX_MESSAGES_PER_LLM_CALL=1)
    middleware = create_athlete_chat_middleware(settings=settings)  # type: ignore[arg-type]
    request = _request(
        messages=[
            HumanMessage(content="one"),
            AIMessage(content="two"),
        ],
        state={
            "conversation_id": "conversation-123",
            "task_id": "task-123",
            "user_message_content": "one",
        },
    )

    async def handler(updated_request: ModelRequest):
        return "ok"

    with pytest.raises(ValidationError):
        await middleware.awrap_model_call(request, handler)
