"""Read-only dashboard insight tools over sanitized analytics snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import structlog
from langchain.tools import ToolRuntime
from langchain_core.tools import StructuredTool

from app.agents.runtime_context import DashboardInsightsRuntimeContext

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DashboardInsightsToolProfile:
    """Configuration for dashboard insight runtime tools."""

    tool_name: str
    description: str
    unavailable_message: str = "Dashboard analytics snapshot unavailable."


DASHBOARD_INSIGHTS_METRIC_TOOL_PROFILE = DashboardInsightsToolProfile(
    tool_name="inspect_dashboard_metric",
    description=(
        "Inspect a specific metric from the sanitized dashboard analytics snapshot. "
        "Use this to verify exact query volume, unanswered count, top topics, or "
        "risk counts before writing dashboard insight output."
    ),
)


DASHBOARD_INSIGHTS_QUERY_EXAMPLES_TOOL_PROFILE = DashboardInsightsToolProfile(
    tool_name="list_anonymized_query_examples",
    description=(
        "List bounded anonymized query examples from the current dashboard "
        "analytics snapshot, optionally filtered by topic or risk label."
    ),
)


def create_dashboard_insights_metric_tool(
    profile: DashboardInsightsToolProfile,
) -> StructuredTool:
    """Create a read-only metric inspection tool."""

    async def _inspect(metric_name: str, runtime: ToolRuntime) -> str:
        context = _runtime_context(runtime, profile=profile)
        if context is None or context.analytics_snapshot is None:
            return profile.unavailable_message
        summary = context.analytics_snapshot.summary
        metric = metric_name.strip().lower()
        if metric in {"query_volume", "volume"}:
            return f"query_volume={summary.query_volume}"
        if metric in {"unanswered_count", "unanswered"}:
            return f"unanswered_count={summary.unanswered_count}"
        if metric in {"top_topics", "topics"}:
            return ", ".join(
                f"{item.label}={item.count}" for item in summary.top_topics
            ) or "No topic counts."
        if metric in {"risk_counts", "risks"}:
            return ", ".join(
                f"{label}={count}" for label, count in summary.risk_counts.items()
            ) or "No risk counts."
        return (
            "Supported metrics: query_volume, unanswered_count, top_topics, "
            "risk_counts."
        )

    return StructuredTool.from_function(
        coroutine=_inspect,
        name=profile.tool_name,
        description=profile.description,
    )


def create_dashboard_insights_query_examples_tool(
    profile: DashboardInsightsToolProfile,
) -> StructuredTool:
    """Create a read-only anonymized query examples tool."""

    async def _list_examples(
        runtime: ToolRuntime,
        topic_label: str | None = None,
        risk_label: str | None = None,
        unanswered_only: bool = False,
        limit: int = 5,
    ) -> str:
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
    )


def _runtime_context(
    runtime: ToolRuntime,
    *,
    profile: DashboardInsightsToolProfile,
) -> DashboardInsightsRuntimeContext | None:
    context = getattr(runtime, "context", None)
    if isinstance(context, DashboardInsightsRuntimeContext):
        return context
    logger.warning(
        "dashboard_insights_tool_missing_runtime_context",
        tool_name=profile.tool_name,
        context_type=type(context).__name__ if context is not None else None,
    )
    return None


def _snapshot_queries(snapshot: Any) -> list[Any]:
    queries = getattr(snapshot, "queries", [])
    return list(queries) if isinstance(queries, Sequence) else []


def _format_query(query: Any) -> str:
    return "\n".join(
        [
            f"Message ID: {_query_value(query, 'message_id')}",
            f"Question: {_query_value(query, 'text')}",
            "Topics: " + (_csv(_query_list(query, "topic_labels")) or "none"),
            "Risks: " + (_csv(_query_list(query, "risk_labels")) or "none"),
            f"Unanswered reason: {_query_value(query, 'unanswered_reason') or 'none'}",
        ]
    )


def _query_value(query: Any, key: str) -> Any:
    if isinstance(query, dict):
        return query.get(key)
    return getattr(query, key, None)


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
