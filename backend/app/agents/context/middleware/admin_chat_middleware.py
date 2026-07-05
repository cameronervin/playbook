"""Admin chat middleware for compact sanitized context injection."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import structlog
from langchain.agents.middleware import ModelRequest, wrap_model_call
from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agents.context.token_budget import truncate_to_token_budget
from app.agents.guardrails.guardrails import assert_message_loop_bounded
from app.core.config import Settings

logger = structlog.get_logger(__name__)


def create_admin_chat_middleware(settings: Settings | None = None) -> Callable:
    """Create middleware that injects bounded admin analytics context."""

    @wrap_model_call
    async def admin_chat_context(
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        state = request.state or {}
        session_id = _string_value(state.get("session_id"), "unknown")
        valid_messages, filtered_count = _filter_blank_messages(request.messages)
        assert_message_loop_bounded(
            valid_messages,
            phase="admin_chat",
            run_id=session_id,
            settings=settings,
        )
        if filtered_count:
            logger.info(
                "admin_chat_blank_messages_filtered",
                session_id=session_id,
                filtered_count=filtered_count,
            )

        snapshot_context = _string_value(state.get("snapshot_context"))
        insight_context = _string_value(state.get("dashboard_insight_context"))
        max_tokens = getattr(settings, "ADMIN_CHAT_CONTEXT_MAX_TOKENS", None)
        if max_tokens is not None:
            snapshot_context = truncate_to_token_budget(
                snapshot_context,
                int(max_tokens),
            )
            insight_context = truncate_to_token_budget(
                insight_context,
                max(500, int(max_tokens) // 2),
            )
        messages = [
            *valid_messages,
            HumanMessage(
                content=_runtime_context(
                    state=state,
                    snapshot_context=snapshot_context,
                    insight_context=insight_context,
                )
            ),
        ]
        return await handler(request.override(messages=messages))

    return admin_chat_context


def _filter_blank_messages(
    messages: Sequence[BaseMessage],
) -> tuple[list[BaseMessage], int]:
    valid_messages: list[BaseMessage] = []
    filtered_count = 0
    for message in messages:
        if isinstance(message, (SystemMessage, ToolMessage)):
            valid_messages.append(message)
            continue
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            valid_messages.append(message)
            continue
        content = getattr(message, "content", "")
        if _content_has_text(content):
            valid_messages.append(message)
        else:
            filtered_count += 1
    return valid_messages, filtered_count


def _runtime_context(
    *,
    state: dict[str, Any],
    snapshot_context: str,
    insight_context: str,
) -> str:
    return "\n".join(
        [
            "## Admin Chat Runtime Context",
            f"Session ID: {_string_value(state.get('session_id'), 'unknown')}",
            f"Organization ID: {_string_value(state.get('organization_id'), 'unknown')}",
            f"Window start: {_string_value(state.get('window_start'), 'unknown')}",
            f"Window end: {_string_value(state.get('window_end'), 'unknown')}",
            "",
            "### Question",
            _string_value(state.get("question"), "unknown"),
            "",
            "### Available Snapshot Facts",
            _section_text(snapshot_context, "No analytics snapshot facts available."),
            "",
            "### Completed Dashboard Insights",
            _section_text(
                insight_context,
                "No completed dashboard insights overlap this window.",
            ),
            "",
            "### Allowed References",
            _string_value(state.get("allowed_references"), "[]"),
            "",
            "### Tool Guidance Reminder",
            (
                "Data tools are optional. If the available snapshot facts or "
                "completed dashboard insights already answer the question, use "
                "the final structured response tool without calling data tools."
            ),
            (
                "Call inspect_admin_metric only for exact counts or summary "
                "metrics; call list_anonymized_queries only for examples, "
                "confusion themes, or unanswered gaps; call "
                "list_dashboard_insights only for stored generated insights, "
                "recommendations, or attention areas."
            ),
            (
                "After a relevant data tool result, produce the final structured "
                "response unless the user asked for a different data type. Do "
                "not call the same data tool with equivalent arguments twice."
            ),
        ]
    )


def _content_has_text(content: Any) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(_content_has_text(part) for part in content)
    if isinstance(content, dict):
        return any(_content_has_text(value) for value in content.values())
    return content is not None and bool(str(content).strip())


def _string_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _section_text(value: str, default: str) -> str:
    text = _string_value(value, default)
    lines = text.splitlines()
    if lines and lines[0].strip() in {
        "## Admin Analytics Snapshot",
        "## Completed Dashboard Insights",
    }:
        cleaned = "\n".join(lines[1:]).strip()
        return cleaned or default
    return text
