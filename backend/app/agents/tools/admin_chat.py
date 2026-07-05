"""Read-only admin chat tools over sanitized analytics context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import structlog
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.agents.runtime_context import AdminChatRuntimeContext

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AdminChatToolProfile:
    """Configuration for admin chat runtime tools."""

    tool_name: str
    description: str
    unavailable_message: str = "Admin chat analytics context unavailable."


ADMIN_CHAT_METRIC_TOOL_PROFILE = AdminChatToolProfile(
    tool_name="inspect_admin_metric",
    description=(
        "Inspect an exact metric from the current sanitized admin analytics "
        "snapshot. Use this for query volume, unanswered count, top topics, or "
        "risk counts."
    ),
)


ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE = AdminChatToolProfile(
    tool_name="list_anonymized_queries",
    description=(
        "List bounded anonymized query examples from the current analytics "
        "snapshot, optionally filtered by topic, risk, or unanswered status."
    ),
)


ADMIN_CHAT_DASHBOARD_INSIGHTS_TOOL_PROFILE = AdminChatToolProfile(
    tool_name="list_dashboard_insights",
    description=(
        "List completed dashboard insight outputs that overlap the current "
        "admin chat window."
    ),
)


class AdminChatMetricInput(BaseModel):
    """Arguments for inspecting exact admin analytics metrics."""

    model_config = ConfigDict(extra="allow")

    metric_name: str = Field(
        description=(
            "Accepted values: analytics.summary, summary, query_volume, "
            "unanswered_count, top_topics, risk_counts. Use "
            "metric:analytics.summary only as a reference/citation, not as the "
            "metric_name argument."
        )
    )


class AdminChatQueryExamplesInput(BaseModel):
    """Arguments for listing bounded anonymized query examples."""

    model_config = ConfigDict(extra="allow")

    topic_label: str | None = Field(
        default=None,
        description=(
            "Optional topic label filter for confusion themes or representative "
            "questions. Leave empty unless the user asks for a topic slice."
        ),
    )
    risk_label: str | None = Field(
        default=None,
        description=(
            "Optional risk label filter for representative questions. Leave empty "
            "unless the user asks for a risk slice."
        ),
    )
    unanswered_only: bool = Field(
        default=False,
        description=(
            "Set true only when the user asks for unanswered gaps or examples "
            "that did not receive a supported answer."
        ),
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description=(
            "Maximum number of representative questions to return for examples "
            "or confusion themes. Use a small value unless the user asks for more."
        ),
    )


class AdminChatDashboardInsightsInput(BaseModel):
    """Arguments for listing completed dashboard insight outputs."""

    model_config = ConfigDict(extra="allow")

    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description=(
            "Maximum number of stored generated insights, recommendations, or "
            "attention areas to return from the selected window."
        ),
    )


def create_admin_chat_metric_tool(profile: AdminChatToolProfile) -> StructuredTool:
    """Create a read-only admin metric inspection tool."""

    async def _inspect(
        metric_name: str,
        runtime: ToolRuntime,
    ) -> str:
        _log_data_tool_call(
            runtime,
            tool_name=profile.tool_name,
            args={"metric_name": metric_name},
        )
        context = _runtime_context(runtime, profile=profile)
        if context is None or context.analytics_snapshot is None:
            return profile.unavailable_message
        summary = context.analytics_snapshot.summary
        metric = metric_name.strip().lower()
        if metric in {"analytics.summary", "summary"}:
            return "\n".join(
                [
                    f"query_volume={summary.query_volume}",
                    f"unanswered_count={summary.unanswered_count}",
                    "top_topics="
                    + (_format_label_counts(summary.top_topics) or "none"),
                    "risk_counts="
                    + (_format_risk_counts(summary.risk_counts) or "none"),
                    "Reference: metric:analytics.summary",
                ]
            )
        if metric in {"query_volume", "volume"}:
            return f"query_volume={summary.query_volume}\nReference: metric:analytics.summary"
        if metric in {"unanswered_count", "unanswered"}:
            return (
                f"unanswered_count={summary.unanswered_count}\n"
                "Reference: metric:analytics.summary"
            )
        if metric in {"top_topics", "topics"}:
            return (
                ", ".join(f"{item.label}={item.count}" for item in summary.top_topics)
                or "No topic counts."
            ) + "\nReference: metric:analytics.summary"
        if metric in {"risk_counts", "risks"}:
            return (
                ", ".join(
                    f"{label}={count}" for label, count in summary.risk_counts.items()
                )
                or "No risk counts."
            ) + "\nReference: metric:analytics.summary"
        return (
            "Supported metrics: analytics.summary, query_volume, "
            "unanswered_count, top_topics, risk_counts."
        )

    return StructuredTool.from_function(
        coroutine=_inspect,
        name=profile.tool_name,
        description=profile.description,
        args_schema=AdminChatMetricInput,
    )


def create_admin_chat_query_examples_tool(
    profile: AdminChatToolProfile,
) -> StructuredTool:
    """Create a read-only anonymized query examples tool."""

    async def _list_examples(
        runtime: ToolRuntime,
        topic_label: str | None = None,
        risk_label: str | None = None,
        unanswered_only: bool = False,
        limit: int = 5,
    ) -> str:
        _log_data_tool_call(
            runtime,
            tool_name=profile.tool_name,
            args={
                "topic_label": topic_label,
                "risk_label": risk_label,
                "unanswered_only": unanswered_only,
                "limit": limit,
            },
        )
        context = _runtime_context(runtime, profile=profile)
        if context is None or context.analytics_snapshot is None:
            return profile.unavailable_message
        queries = _snapshot_queries(context.analytics_snapshot)
        topic = _clean_filter(topic_label)
        risk = _clean_filter(risk_label)
        filtered: list[Any] = []
        for query in queries:
            if topic and topic not in _query_list(query, "topic_labels"):
                continue
            if risk and risk not in _query_list(query, "risk_labels"):
                continue
            if unanswered_only and not _query_value(query, "unanswered_reason"):
                continue
            filtered.append(query)
            if len(filtered) >= max(1, min(limit, 10)):
                break
        if not filtered:
            return "No matching anonymized query examples in the snapshot."
        return "\n\n".join(_format_query(query) for query in filtered)

    return StructuredTool.from_function(
        coroutine=_list_examples,
        name=profile.tool_name,
        description=profile.description,
        args_schema=AdminChatQueryExamplesInput,
    )


def create_admin_chat_dashboard_insights_tool(
    profile: AdminChatToolProfile,
) -> StructuredTool:
    """Create a read-only dashboard insight listing tool."""

    async def _list_insights(
        runtime: ToolRuntime,
        limit: int = 5,
    ) -> str:
        _log_data_tool_call(
            runtime,
            tool_name=profile.tool_name,
            args={"limit": limit},
        )
        context = _runtime_context(runtime, profile=profile)
        if context is None:
            return profile.unavailable_message
        insights = context.dashboard_insights[: max(1, min(limit, 10))]
        if not insights:
            return "No completed dashboard insights overlap this window."
        return "\n\n".join(_format_dashboard_insight(insight) for insight in insights)

    return StructuredTool.from_function(
        coroutine=_list_insights,
        name=profile.tool_name,
        description=profile.description,
        args_schema=AdminChatDashboardInsightsInput,
    )


def _runtime_context(
    runtime: ToolRuntime,
    *,
    profile: AdminChatToolProfile,
) -> AdminChatRuntimeContext | None:
    context = getattr(runtime, "context", None)
    if isinstance(context, AdminChatRuntimeContext):
        return context
    logger.warning(
        "admin_chat_tool_missing_runtime_context",
        tool_name=profile.tool_name,
        context_type=type(context).__name__ if context is not None else None,
    )
    return None


def _log_data_tool_call(
    runtime: ToolRuntime,
    *,
    tool_name: str,
    args: dict[str, Any],
) -> None:
    state = _runtime_mapping(getattr(runtime, "state", None))
    config = _runtime_mapping(getattr(runtime, "config", None))
    configurable = _runtime_mapping(config.get("configurable"))
    logger.info(
        "admin_chat_data_tool_called",
        tool_name=tool_name,
        task_id=_string_or_none(state.get("task_id") or configurable.get("task_id")),
        session_id=_string_or_none(
            state.get("session_id") or configurable.get("session_id")
        ),
        organization_id=_string_or_none(
            state.get("organization_id") or configurable.get("organization_id")
        ),
        call_index=_tool_call_index(state),
        args=_safe_tool_args(args),
    )


def _tool_call_index(state: dict[str, Any]) -> int:
    messages = state.get("messages")
    if not isinstance(messages, Sequence):
        return 1
    count = 0
    for message in messages:
        if not isinstance(message, BaseMessage):
            continue
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            count += len(message.tool_calls)
    return max(1, count)


def _safe_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    safe_args: dict[str, Any] = {}
    for key, value in args.items():
        if isinstance(value, str):
            safe_args[key] = value[:120]
            continue
        if value is None or isinstance(value, (bool, int, float)):
            safe_args[key] = value
            continue
        safe_args[key] = str(value)[:120]
    return safe_args


def _runtime_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _snapshot_queries(snapshot: Any) -> list[Any]:
    queries = getattr(snapshot, "queries", [])
    return list(queries) if isinstance(queries, Sequence) else []


def _format_query(query: Any) -> str:
    message_id = _query_reference_id(query)
    return "\n".join(
        [
            f"Message ID: {message_id}",
            f"Question: {_query_value(query, 'text')}",
            "Topics: " + (_csv(_query_list(query, "topic_labels")) or "none"),
            "Risks: " + (_csv(_query_list(query, "risk_labels")) or "none"),
            f"Answer type: {_query_value(query, 'answer_type') or 'unknown'}",
            f"Unanswered reason: {_query_value(query, 'unanswered_reason') or 'none'}",
            f"Reference: query:{message_id}",
        ]
    )


def _format_dashboard_insight(insight: Any) -> str:
    insight_id = _insight_value(insight, "id")
    return "\n".join(
        [
            f"Insight ID: {insight_id}",
            f"Summary: {_insight_value(insight, 'summary')}",
            f"Reference: dashboard_insight:{insight_id}",
        ]
    )


def _query_value(query: Any, key: str) -> Any:
    if isinstance(query, dict):
        return query.get(key)
    return getattr(query, key, None)


def _query_reference_id(query: Any) -> str:
    display_id = _query_value(query, "display_message_id")
    if display_id is not None and str(display_id).strip():
        return str(display_id).strip()
    return str(_query_value(query, "message_id") or "")


def _insight_value(insight: Any, key: str) -> Any:
    if isinstance(insight, dict):
        return insight.get(key)
    return getattr(insight, key, None)


def _query_list(query: Any, key: str) -> list[str]:
    value = _query_value(query, key)
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Sequence):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _clean_filter(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _csv(values: Sequence[str]) -> str:
    return ", ".join(values)


def _format_label_counts(values: Sequence[Any]) -> str:
    return ", ".join(
        f"{_item_value(item, 'label')}={_item_value(item, 'count')}"
        for item in values
        if _item_value(item, "label") not in {None, ""}
    )


def _format_risk_counts(values: dict[str, int]) -> str:
    return ", ".join(f"{label}={count}" for label, count in values.items())


def _item_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)
