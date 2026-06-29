"""Dashboard insights middleware for compact sanitized context injection."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import structlog
from langchain.agents.middleware import ModelRequest, wrap_model_call
from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agents.context.token_budget import truncate_to_token_budget
from app.agents.guardrails.guardrails import assert_message_loop_bounded
from app.core.config import Settings

logger = structlog.get_logger(__name__)


def create_dashboard_insights_middleware(settings: Settings | None = None) -> Callable:
    """Create middleware that injects bounded dashboard snapshot context."""

    @wrap_model_call
    async def dashboard_insights_context(
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        state = request.state or {}
        run_id = _string_value(state.get("run_id"), "unknown")
        valid_messages, filtered_count = _filter_blank_messages(request.messages)
        assert_message_loop_bounded(
            valid_messages,
            phase="dashboard_insights",
            run_id=run_id,
            settings=settings,
        )
        if filtered_count:
            logger.info(
                "dashboard_insights_blank_messages_filtered",
                run_id=run_id,
                filtered_count=filtered_count,
            )

        snapshot_context = _string_value(state.get("snapshot_context"))
        max_tokens = getattr(settings, "DASHBOARD_INSIGHTS_CONTEXT_MAX_TOKENS", None)
        if max_tokens is not None:
            snapshot_context = truncate_to_token_budget(
                snapshot_context,
                int(max_tokens),
            )
        messages = [
            *valid_messages,
            HumanMessage(content=_runtime_context(state, snapshot_context)),
        ]
        return await handler(request.override(messages=messages))

    return dashboard_insights_context


def _filter_blank_messages(
    messages: Sequence[BaseMessage],
) -> tuple[list[BaseMessage], int]:
    valid_messages: list[BaseMessage] = []
    filtered_count = 0
    for message in messages:
        if isinstance(message, (SystemMessage, ToolMessage)):
            valid_messages.append(message)
            continue
        content = getattr(message, "content", "")
        if _content_has_text(content):
            valid_messages.append(message)
        else:
            filtered_count += 1
    return valid_messages, filtered_count


def _runtime_context(state: dict[str, Any], snapshot_context: str) -> str:
    return "\n".join(
        [
            "## Dashboard Insight Runtime Context",
            f"Run ID: {_string_value(state.get('run_id'), 'unknown')}",
            f"Organization ID: {_string_value(state.get('organization_id'), 'unknown')}",
            f"Window start: {_string_value(state.get('window_start'), 'unknown')}",
            f"Window end: {_string_value(state.get('window_end'), 'unknown')}",
            f"Source filters: {_string_value(state.get('source_filters'), '{}')}",
            "",
            snapshot_context,
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
