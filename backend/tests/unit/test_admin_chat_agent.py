from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from langchain.tools import ToolRuntime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict

from app.agents.chains.admin_chat_chain import create_admin_chat_chain
from app.agents.context.prompt_composers.admin_chat_prompt_composer import (
    build_admin_chat_prompt,
)
from app.agents.guardrails.guardrails import assert_message_loop_bounded
from app.agents.nodes import admin_chat as admin_chat_nodes
from app.agents.nodes.admin_chat import create_admin_chat_nodes
from app.agents.runtime_context import AdminChatRuntimeContext
from app.agents.states.admin_chat_state import (
    AdminChatState,
    AdminChatStructuredResponse,
)
from app.agents.tools.admin_chat import (
    ADMIN_CHAT_DASHBOARD_INSIGHTS_TOOL_PROFILE,
    ADMIN_CHAT_METRIC_TOOL_PROFILE,
    ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE,
    create_admin_chat_dashboard_insights_tool,
    create_admin_chat_metric_tool,
    create_admin_chat_query_examples_tool,
)
from app.core.exceptions import ValidationError
from app.schemas.admin_analytics import (
    AdminAnalyticsQueryResponse,
    AdminAnalyticsSnapshot,
    AdminAnalyticsSummaryResponse,
    LabelCount,
)

QUERY_ONE_ID = UUID("00000000-0000-0000-0000-000000000001")
QUERY_TWO_ID = UUID("00000000-0000-0000-0000-000000000002")


class AnalyticsSummaryToolCallingModel(BaseChatModel):
    """Fake model that uses a real admin metric tool before structured output."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    calls: int = 0
    metric_tool_name: str = ""
    structured_tool_name: str = ""

    @property
    def _llm_type(self) -> str:
        return "analytics-summary-tool-calling"

    def bind_tools(
        self,
        tools: list[Any],
        **_: Any,
    ) -> "AnalyticsSummaryToolCallingModel":
        self.metric_tool_name = next(
            str(tool.name) for tool in tools if str(tool.name) == "inspect_admin_metric"
        )
        self.structured_tool_name = str(tools[-1].name)
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **_: Any,
    ) -> ChatResult:
        self.calls += 1
        if self.calls == 1:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.metric_tool_name,
                        "args": {"metric_name": "analytics.summary"},
                        "id": "metric_call_1",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.structured_tool_name,
                        "args": {
                            "answer": "There were 12 queries, led by NIL.",
                            "answer_type": "analytics_answer",
                            "references": [
                                {"type": "metric", "id": "analytics.summary"}
                            ],
                        },
                        "id": "structured_call_1",
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


class DirectStructuredAdminChatModel(BaseChatModel):
    """Fake model that answers from runtime context without data tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    calls: int = 0
    structured_tool_name: str = ""
    bound_tool_names: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "direct-structured-admin-chat"

    def bind_tools(
        self,
        tools: list[Any],
        **_: Any,
    ) -> "DirectStructuredAdminChatModel":
        self.bound_tool_names = [str(tool.name) for tool in tools]
        self.structured_tool_name = str(tools[-1].name)
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **_: Any,
    ) -> ChatResult:
        self.calls += 1
        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": self.structured_tool_name,
                    "args": {
                        "answer": "The snapshot already shows 12 queries.",
                        "answer_type": "analytics_answer",
                        "references": [{"type": "metric", "id": "analytics.summary"}],
                    },
                    "id": "structured_call_1",
                    "type": "tool_call",
                }
            ],
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


class QueryExamplesToolCallingModel(BaseChatModel):
    """Fake model that uses query examples before structured output."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    calls: int = 0
    query_tool_name: str = ""
    structured_tool_name: str = ""

    @property
    def _llm_type(self) -> str:
        return "query-examples-tool-calling"

    def bind_tools(
        self,
        tools: list[Any],
        **_: Any,
    ) -> "QueryExamplesToolCallingModel":
        self.query_tool_name = next(
            str(tool.name)
            for tool in tools
            if str(tool.name) == "list_anonymized_queries"
        )
        self.structured_tool_name = str(tools[-1].name)
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **_: Any,
    ) -> ChatResult:
        self.calls += 1
        if self.calls == 1:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.query_tool_name,
                        "args": {"topic_label": "nil", "limit": 3},
                        "id": "query_call_1",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.structured_tool_name,
                        "args": {
                            "answer": "NIL disclosure timing is the clearest example theme.",
                            "answer_type": "analytics_answer",
                            "references": [{"type": "query", "id": str(QUERY_ONE_ID)}],
                        },
                        "id": "structured_call_1",
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


class FakeStreamService:
    def __init__(self) -> None:
        self.chunks: list[str] = []
        self.progresses: list[str] = []

    async def publish_progress(
        self,
        task_id: str,
        *,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.progresses.append(status)

    async def publish_chunk(self, task_id: str, *, content: str) -> None:
        self.chunks.append(content)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


def _tool_runtime(context: object | None = None) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=context,
        config={},
        stream_writer=lambda _: None,
        tool_call_id=None,
        store=None,
    )


def _snapshot(
    queries: list[AdminAnalyticsQueryResponse] | None = None,
) -> AdminAnalyticsSnapshot:
    return AdminAnalyticsSnapshot(
        summary=AdminAnalyticsSummaryResponse(
            window_start=datetime(2026, 6, 24, tzinfo=UTC),
            window_end=datetime(2026, 7, 1, tzinfo=UTC),
            query_volume=12,
            unanswered_count=3,
            top_topics=[LabelCount(label="nil", count=7)],
            risk_counts={"compliance": 4},
        ),
        queries=queries or [],
    )


def _query(
    *,
    message_id: UUID,
    text: str,
    topic_labels: list[str],
    risk_labels: list[str],
    unanswered_reason: str | None = None,
) -> AdminAnalyticsQueryResponse:
    return AdminAnalyticsQueryResponse(
        message_id=message_id,
        anonymous_user_key=f"anon-{message_id.hex[:6]}",
        text=text,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        topic_labels=topic_labels,
        risk_labels=risk_labels,
        unanswered_reason=unanswered_reason,
    )


def _runtime_context(
    snapshot: AdminAnalyticsSnapshot,
    settings: Any,
) -> AdminChatRuntimeContext:
    return AdminChatRuntimeContext(
        session=object(),
        settings=settings,
        stream_service=object(),
        analytics_snapshot=snapshot,
    )


def test_admin_chat_prompt_includes_tool_use_policy_and_stop_guidance() -> None:
    prompt = build_admin_chat_prompt(
        "admin_chat",
        [
            "inspect_admin_metric",
            "list_anonymized_queries",
            "list_dashboard_insights",
        ],
    )

    assert "<tool_use_policy>" in prompt
    assert "Read the runtime context first" in prompt
    assert "Data tools are optional" in prompt
    assert "final structured response tool" in prompt
    assert "After a relevant data tool result" in prompt
    assert "Do not call the same data tool with equivalent arguments twice" in prompt
    assert "Every final reference must come from Allowed References" in prompt
    assert "Include references for every metric, query, or dashboard insight used" in prompt


def test_admin_chat_tools_expose_described_argument_schemas() -> None:
    metric_tool = create_admin_chat_metric_tool(ADMIN_CHAT_METRIC_TOOL_PROFILE)
    query_tool = create_admin_chat_query_examples_tool(
        ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE
    )
    insights_tool = create_admin_chat_dashboard_insights_tool(
        ADMIN_CHAT_DASHBOARD_INSIGHTS_TOOL_PROFILE
    )

    assert [metric_tool.name, query_tool.name, insights_tool.name] == [
        "inspect_admin_metric",
        "list_anonymized_queries",
        "list_dashboard_insights",
    ]
    metric_description = metric_tool.args_schema.model_fields["metric_name"].description
    assert metric_description is not None
    assert "Accepted values" in metric_description
    assert "analytics.summary" in metric_description
    assert "metric:analytics.summary" in metric_description

    query_fields = query_tool.args_schema.model_fields
    assert "confusion themes" in query_fields["topic_label"].description
    assert "unanswered gaps" in query_fields["unanswered_only"].description
    assert "representative questions" in query_fields["limit"].description

    insights_description = insights_tool.args_schema.model_fields["limit"].description
    assert insights_description is not None
    assert "stored generated insights" in insights_description


@pytest.mark.asyncio
async def test_admin_chat_metric_tool_accepts_analytics_summary_alias(
    test_settings,
) -> None:
    tool = create_admin_chat_metric_tool(ADMIN_CHAT_METRIC_TOOL_PROFILE)
    snapshot = _snapshot()

    result = await tool.ainvoke(
        {
            "runtime": _tool_runtime(_runtime_context(snapshot, test_settings)),
            "metric_name": "analytics.summary",
        }
    )

    assert "query_volume=12" in result
    assert "unanswered_count=3" in result
    assert "top_topics=nil=7" in result
    assert "risk_counts=compliance=4" in result
    assert "Reference: metric:analytics.summary" in result


@pytest.mark.asyncio
async def test_admin_chat_metric_tool_accepts_summary_alias(test_settings) -> None:
    tool = create_admin_chat_metric_tool(ADMIN_CHAT_METRIC_TOOL_PROFILE)
    snapshot = _snapshot()

    result = await tool.ainvoke(
        {
            "runtime": _tool_runtime(_runtime_context(snapshot, test_settings)),
            "metric_name": "summary",
        }
    )

    assert "query_volume=12" in result
    assert "Reference: metric:analytics.summary" in result


@pytest.mark.asyncio
async def test_admin_chat_chain_can_answer_directly_from_runtime_context(
    test_settings,
) -> None:
    model = DirectStructuredAdminChatModel()
    chain = create_admin_chat_chain(
        chat_model=model,
        tools=[
            create_admin_chat_metric_tool(ADMIN_CHAT_METRIC_TOOL_PROFILE),
            create_admin_chat_query_examples_tool(
                ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE
            ),
        ],
        settings=test_settings,
    )

    result = await chain.ainvoke(
        {
            "messages": [HumanMessage(content="How many queries this week?")],
            "task_id": "task-1",
            "session_id": "session-1",
            "organization_id": "org-1",
            "window_start": "2026-06-24T00:00:00+00:00",
            "window_end": "2026-07-01T00:00:00+00:00",
            "question": "How many queries this week?",
            "snapshot_context": "Query volume: 12",
            "allowed_references": [{"type": "metric", "id": "analytics.summary"}],
        },
        config={"recursion_limit": 5},
        context=_runtime_context(_snapshot(), test_settings),
    )

    assert "inspect_admin_metric" in model.bound_tool_names
    assert result["structured_response"] == AdminChatStructuredResponse(
        answer="The snapshot already shows 12 queries.",
        answer_type="analytics_answer",
        references=[{"type": "metric", "id": "analytics.summary"}],
    )
    assert model.calls == 1


@pytest.mark.asyncio
async def test_admin_chat_chain_handles_analytics_summary_tool_call(
    test_settings,
) -> None:
    model = AnalyticsSummaryToolCallingModel()
    chain = create_admin_chat_chain(
        chat_model=model,
        tools=[create_admin_chat_metric_tool(ADMIN_CHAT_METRIC_TOOL_PROFILE)],
        settings=test_settings,
    )

    result = await chain.ainvoke(
        {
            "messages": [HumanMessage(content="What is happening this week?")],
            "task_id": "task-1",
            "session_id": "session-1",
            "organization_id": "org-1",
            "window_start": "2026-06-24T00:00:00+00:00",
            "window_end": "2026-07-01T00:00:00+00:00",
            "question": "What is happening this week?",
            "snapshot_context": "Query volume: 12",
            "allowed_references": [{"type": "metric", "id": "analytics.summary"}],
        },
        config={"recursion_limit": 5},
        context=_runtime_context(_snapshot(), test_settings),
    )

    assert result["structured_response"] == AdminChatStructuredResponse(
        answer="There were 12 queries, led by NIL.",
        answer_type="analytics_answer",
        references=[{"type": "metric", "id": "analytics.summary"}],
    )
    assert model.calls == 2


@pytest.mark.asyncio
async def test_admin_chat_chain_uses_query_examples_for_confusion_questions(
    test_settings,
) -> None:
    model = QueryExamplesToolCallingModel()
    chain = create_admin_chat_chain(
        chat_model=model,
        tools=[
            create_admin_chat_query_examples_tool(
                ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE
            )
        ],
        settings=test_settings,
    )
    snapshot = _snapshot(
        queries=[
            _query(
                message_id=QUERY_ONE_ID,
                text="When do I disclose an NIL deal?",
                topic_labels=["nil"],
                risk_labels=["compliance"],
            )
        ]
    )

    result = await chain.ainvoke(
        {
            "messages": [
                HumanMessage(content="What are athletes confused about for NIL?")
            ],
            "task_id": "task-1",
            "session_id": "session-1",
            "organization_id": "org-1",
            "window_start": "2026-06-24T00:00:00+00:00",
            "window_end": "2026-07-01T00:00:00+00:00",
            "question": "What are athletes confused about for NIL?",
            "snapshot_context": "Top topics: nil=7",
            "allowed_references": [{"type": "query", "id": str(QUERY_ONE_ID)}],
        },
        config={"recursion_limit": 5},
        context=_runtime_context(snapshot, test_settings),
    )

    assert result["structured_response"] == AdminChatStructuredResponse(
        answer="NIL disclosure timing is the clearest example theme.",
        answer_type="analytics_answer",
        references=[{"type": "query", "id": str(QUERY_ONE_ID)}],
    )
    assert model.calls == 2


@pytest.mark.asyncio
async def test_admin_chat_query_tool_reads_runtime_snapshot(test_settings) -> None:
    tool = create_admin_chat_query_examples_tool(ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE)
    snapshot = _snapshot(
        queries=[
            _query(
                message_id=QUERY_ONE_ID,
                text="When do I disclose an NIL deal?",
                topic_labels=["nil"],
                risk_labels=["compliance"],
            ),
            _query(
                message_id=QUERY_TWO_ID,
                text="Can recruiting staff text this prospect?",
                topic_labels=["recruiting"],
                risk_labels=["recruiting"],
                unanswered_reason="unsupported",
            ),
        ]
    )

    result = await tool.ainvoke(
        {
            "runtime": _tool_runtime(_runtime_context(snapshot, test_settings)),
            "topic_label": "nil",
            "limit": 5,
        }
    )

    assert str(QUERY_ONE_ID) in result
    assert "When do I disclose" in result
    assert str(QUERY_TWO_ID) not in result


@pytest.mark.asyncio
async def test_admin_chat_query_tool_requires_runtime_context() -> None:
    tool = create_admin_chat_query_examples_tool(ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE)

    result = await tool.ainvoke({"runtime": _tool_runtime(), "limit": 5})

    assert result == ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE.unavailable_message


@pytest.mark.asyncio
async def test_admin_chat_loop_guard_fallback_persists_unsupported_response(
    monkeypatch: pytest.MonkeyPatch,
    test_settings,
) -> None:
    assistant_message_id = uuid4()
    captured: dict[str, Any] = {}

    class LoopingChain:
        async def ainvoke(self, *_: Any, **__: Any) -> dict[str, Any]:
            raise ValidationError(
                "Agent message loop guard triggered for chain 'admin_chat'",
                details={
                    "phase": "admin_chat",
                    "message_count": 61,
                    "max_messages": 60,
                },
            )

    class FakeMessageRepository:
        def __init__(self, session: Any) -> None:
            self.session = session

        async def get(self, message_id: Any) -> Any:
            assert message_id == assistant_message_id
            return SimpleNamespace(id=assistant_message_id, message_metadata={})

        async def update_status_content_references(
            self,
            message: Any,
            *,
            status: str,
            content: str | None = None,
            references: list[dict[str, str]] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            captured.update(
                {
                    "status": status,
                    "content": content,
                    "references": references,
                    "metadata": metadata,
                }
            )

    monkeypatch.setattr(
        admin_chat_nodes,
        "AdminChatMessageRepository",
        FakeMessageRepository,
    )
    nodes = create_admin_chat_nodes(chains={"admin_chat": LoopingChain()})
    session = FakeSession()
    stream_service = FakeStreamService()
    runtime = SimpleNamespace(
        context=AdminChatRuntimeContext(
            session=session,
            settings=test_settings,
            stream_service=stream_service,
            analytics_snapshot=_snapshot(),
        )
    )
    state: AdminChatState = {
        "messages": [HumanMessage(content="testing")],
        "task_id": "task-1",
        "session_id": str(uuid4()),
        "admin_user_id": str(uuid4()),
        "user_message_id": str(uuid4()),
        "assistant_message_id": str(assistant_message_id),
        "organization_id": str(uuid4()),
        "window_start": datetime.now(UTC).isoformat(),
        "window_end": datetime.now(UTC).isoformat(),
        "question": "testing",
        "allowed_references": [{"type": "metric", "id": "analytics.summary"}],
    }

    fallback = await nodes["run_agent"](state, runtime)
    completion = await nodes["save_response"]({**state, **fallback}, runtime)

    assert captured["status"] == "complete"
    assert captured["content"]
    assert captured["metadata"]["answer_type"] == "unsupported"
    assert completion["completion_result"]["answer_type"] == "unsupported"
    assert session.committed is True


def test_admin_chat_loop_guard_details_include_tool_call_summary() -> None:
    settings = SimpleNamespace(AGENT_MAX_MESSAGES_PER_LLM_CALL=2)
    messages = [
        HumanMessage(content="What is happening this week?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "inspect_admin_metric",
                    "args": {"metric_name": "analytics.summary"},
                    "id": "metric_call_1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(content="query_volume=12", tool_call_id="metric_call_1"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "inspect_admin_metric",
                    "args": {"metric_name": "analytics.summary"},
                    "id": "metric_call_2",
                    "type": "tool_call",
                }
            ],
        ),
    ]

    with pytest.raises(ValidationError) as exc_info:
        assert_message_loop_bounded(
            messages,
            phase="admin_chat",
            run_id="session-1",
            settings=settings,  # type: ignore[arg-type]
        )

    assert exc_info.value.details["tool_names"] == ["inspect_admin_metric"]
    assert exc_info.value.details["repeated_tool_call_count"] == 1
    assert exc_info.value.details["ai_tool_call_count"] == 2
    assert exc_info.value.details["tool_message_count"] == 1


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
