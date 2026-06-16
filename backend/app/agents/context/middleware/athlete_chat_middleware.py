"""Athlete chat middleware for compact runtime context and message guardrails."""

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

from app.agents.guardrails.guardrails import assert_message_loop_bounded
from app.core.config import Settings

logger = structlog.get_logger(__name__)


def create_athlete_chat_middleware(settings: Settings | None = None) -> Callable:
    """Create middleware for the structured athlete chat agent.

    The athlete workflow intentionally keeps the bounded history loaded by the
    graph's ``load_state`` node. This middleware removes blank message noise,
    applies the loop guard, and appends compact runtime flags plus any
    pre-retrieved conversation-file snippets prepared by the graph.
    """

    @wrap_model_call
    async def athlete_chat_context(
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        state = request.state or {}
        conversation_id = _string_value(state.get("conversation_id"), "unknown")
        task_id = _string_value(state.get("task_id"), "unknown")
        telemetry_id = (
            conversation_id
            if conversation_id != "unknown"
            else f"task:{task_id}"
        )

        valid_messages, filtered_count = _filter_blank_messages(request.messages)
        assert_message_loop_bounded(
            valid_messages,
            phase="athlete_chat",
            run_id=telemetry_id,
            settings=settings,
        )

        if filtered_count:
            logger.info(
                "athlete_chat_blank_messages_filtered",
                conversation_id=conversation_id,
                task_id=task_id,
                filtered_count=filtered_count,
            )

        appended_context = [HumanMessage(content=_build_runtime_context(state))]
        file_context = _build_conversation_file_context(state)
        if file_context:
            appended_context.append(HumanMessage(content=file_context))
        messages = [*valid_messages, *appended_context]
        return await handler(request.override(messages=messages))

    return athlete_chat_context


def _filter_blank_messages(messages: Sequence[BaseMessage]) -> tuple[list[BaseMessage], int]:
    """Drop blank human/AI messages while preserving tool-call exchanges."""
    valid_messages: list[BaseMessage] = []
    filtered_count = 0

    for message in messages:
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            valid_messages.append(message)
            continue
        if isinstance(message, (SystemMessage, ToolMessage)):
            valid_messages.append(message)
            continue

        content = getattr(message, "content", "")
        if _content_has_text(content):
            valid_messages.append(message)
        else:
            filtered_count += 1

    return valid_messages, filtered_count


def _build_runtime_context(state: dict[str, Any]) -> str:
    """Build compact, non-authoritative context for the active athlete turn."""
    question = _string_value(state.get("user_message_content"), "Unknown")
    requires_kb_support = bool(state.get("requires_kb_support", False))
    topic_labels = _string_list(state.get("topic_labels"))
    risk_labels = _string_list(state.get("risk_labels"))
    attached_file_ids = _string_list(state.get("attached_file_ids"))

    return "\n".join(
        [
            "## Athlete Chat Runtime Context",
            f"Current question: {question}",
            f"Requires KB support: {_bool_text(requires_kb_support)}",
            f"Topic labels: {_csv_or_none(topic_labels)}",
            f"Risk labels: {_csv_or_none(risk_labels)}",
            f"Attached file count: {len(attached_file_ids)}",
            f"Attached file IDs: {_csv_or_none(attached_file_ids)}",
        ]
    )


def _build_conversation_file_context(state: dict[str, Any]) -> str:
    """Return pre-retrieved private file snippets for model-call injection."""
    context = _string_value(state.get("conversation_file_context"))
    return context


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


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Sequence):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _csv_or_none(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "none"
