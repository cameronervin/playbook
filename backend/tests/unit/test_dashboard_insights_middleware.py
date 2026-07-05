from __future__ import annotations

import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.context.middleware.dashboard_insights_middleware import (
    create_dashboard_insights_middleware,
)


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
    middleware = create_dashboard_insights_middleware()

    async def handler(updated_request: ModelRequest):
        captured["messages"] = updated_request.messages
        return "ok"

    await middleware.awrap_model_call(request, handler)
    return captured["messages"]


@pytest.mark.asyncio
async def test_dashboard_insights_middleware_preserves_tool_call_messages() -> None:
    tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "inspect_dashboard_metric",
                "args": {"metric": "query_volume"},
                "id": "tool-call-1",
                "type": "tool_call",
            }
        ],
    )
    tool_result = ToolMessage(content="Query volume: 21", tool_call_id="tool-call-1")

    messages = await _capture_messages(
        _request(
            messages=[
                HumanMessage(content="Generate dashboard insights."),
                AIMessage(content=""),
                HumanMessage(content="   "),
                tool_call,
                tool_result,
            ],
            state={
                "run_id": "run-1",
                "organization_id": "org-1",
                "snapshot_context": "Query volume: 21",
            },
        )
    )

    assert [type(message) for message in messages[:-1]] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
    ]
    assert messages[1].tool_calls == tool_call.tool_calls
    assert messages[2].content == "Query volume: 21"
    assert "## Dashboard Insight Runtime Context" in messages[-1].content
