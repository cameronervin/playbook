from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain.tools import ToolRuntime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict

from app.agents.chains.dashboard_insights_chain import create_dashboard_insights_chain
from app.agents.runtime_context import DashboardInsightsRuntimeContext
from app.agents.states.dashboard_insights_state import (
    DashboardInsightsState,
    DashboardInsightsStructuredResponse,
)
from app.agents.tools.dashboard_insights import (
    DASHBOARD_INSIGHTS_QUERY_EXAMPLES_TOOL_PROFILE,
    create_dashboard_insights_query_examples_tool,
)


class StructuredDashboardInsightsModel(BaseChatModel):
    """Fake model that emits the structured-output tool call requested by LangChain."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_args: dict[str, Any]
    calls: int = 0
    tool_name: str = ""

    @property
    def _llm_type(self) -> str:
        return "structured-dashboard-insights"

    def bind_tools(self, tools: list[Any], **_: Any) -> "StructuredDashboardInsightsModel":
        self.tool_name = str(tools[-1].name)
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **_: Any,
    ) -> ChatResult:
        self.calls += 1
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": self.tool_name,
                                "args": self.tool_args,
                                "id": f"dashboard_call_{self.calls}",
                                "type": "tool_call",
                            }
                        ],
                    )
                )
            ]
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


def _runtime_context(snapshot: FakeSnapshot) -> DashboardInsightsRuntimeContext:
    return DashboardInsightsRuntimeContext(
        session=object(),
        settings=object(),
        analytics_snapshot=snapshot,
    )


@pytest.mark.asyncio
async def test_dashboard_insights_chain_uses_structured_response_and_context(
    test_settings,
) -> None:
    model = StructuredDashboardInsightsModel(
        tool_args={
            "summary": "NIL timing confusion is the top issue.",
            "headline_cards": [
                {
                    "title": "NIL disclosure timing",
                    "value": "2 related questions",
                    "severity": "medium",
                }
            ],
            "topic_breakdown": [{"label": "nil", "count": 2, "examples": []}],
            "unanswered_questions": [],
            "risk_breakdown": [{"label": "compliance", "count": 1}],
            "recommended_attention_areas": [
                "Clarify NIL disclosure timing in athlete guidance."
            ],
            "source_message_ids": [],
        }
    )

    chain = create_dashboard_insights_chain(
        chat_model=model,
        tools=[],
        settings=test_settings,
    )
    result = await chain.ainvoke(
        {
            "messages": [HumanMessage(content="Generate dashboard insights.")],
            "run_id": "run-1",
            "organization_id": "org-1",
            "snapshot_context": "Query volume: 2",
        },
        config={"recursion_limit": 5},
        context=_runtime_context(FakeSnapshot()),
    )

    assert result["structured_response"] == DashboardInsightsStructuredResponse(
        summary="NIL timing confusion is the top issue.",
        headline_cards=[
            {
                "title": "NIL disclosure timing",
                "value": "2 related questions",
                "severity": "medium",
            }
        ],
        topic_breakdown=[{"label": "nil", "count": 2, "examples": []}],
        risk_breakdown=[{"label": "compliance", "count": 1}],
        recommended_attention_areas=[
            "Clarify NIL disclosure timing in athlete guidance."
        ],
    )
    assert model.calls == 1


@pytest.mark.asyncio
async def test_dashboard_query_examples_tool_reads_runtime_snapshot() -> None:
    tool = create_dashboard_insights_query_examples_tool(
        DASHBOARD_INSIGHTS_QUERY_EXAMPLES_TOOL_PROFILE
    )
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
async def test_dashboard_query_examples_tool_requires_runtime_context() -> None:
    tool = create_dashboard_insights_query_examples_tool(
        DASHBOARD_INSIGHTS_QUERY_EXAMPLES_TOOL_PROFILE
    )

    result = await tool.ainvoke({"runtime": _tool_runtime(), "limit": 5})

    assert result == DASHBOARD_INSIGHTS_QUERY_EXAMPLES_TOOL_PROFILE.unavailable_message


def test_dashboard_insights_state_is_json_safe() -> None:
    state: DashboardInsightsState = {
        "run_id": "run-1",
        "organization_id": "org-1",
        "window_start": "2026-06-01T00:00:00+00:00",
        "window_end": "2026-06-08T00:00:00+00:00",
        "source_filters": {"topic_labels": ["nil"]},
        "snapshot_context": "Query volume: 2",
        "source_message_ids": ["message-1"],
    }

    assert "session" not in state
    assert "analytics_snapshot" not in state
