from __future__ import annotations

import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.messages import HumanMessage

from app.agents.context.middleware.admin_chat_middleware import (
    create_admin_chat_middleware,
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
    middleware = create_admin_chat_middleware()

    async def handler(updated_request: ModelRequest):
        captured["messages"] = updated_request.messages
        return "ok"

    await middleware.awrap_model_call(request, handler)
    return captured["messages"]


@pytest.mark.asyncio
async def test_admin_chat_middleware_appends_sectioned_runtime_context() -> None:
    messages = await _capture_messages(
        _request(
            messages=[HumanMessage(content="How many queries this week?")],
            state={
                "session_id": "session-1",
                "organization_id": "org-1",
                "window_start": "2026-06-24T00:00:00+00:00",
                "window_end": "2026-07-01T00:00:00+00:00",
                "question": "How many queries this week?",
                "snapshot_context": "Query volume: 12",
                "dashboard_insight_context": "Summary: NIL timing confusion.",
                "allowed_references": [{"type": "metric", "id": "analytics.summary"}],
            },
        )
    )

    context = messages[-1].content
    assert "## Admin Chat Runtime Context" in context
    assert "### Question" in context
    assert "How many queries this week?" in context
    assert "### Available Snapshot Facts" in context
    assert "Query volume: 12" in context
    assert "### Completed Dashboard Insights" in context
    assert "Summary: NIL timing confusion." in context
    assert "### Allowed References" in context
    assert "metric" in context
    assert "analytics.summary" in context
    assert "### Tool Guidance Reminder" in context
    assert "Data tools are optional" in context
    assert "Do not call the same data tool with equivalent arguments twice" in context
