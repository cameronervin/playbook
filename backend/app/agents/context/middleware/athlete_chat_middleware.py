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
MAX_MANIFEST_FILES = 8
MAX_MANIFEST_SUMMARY_CHARS = 280


def create_athlete_chat_middleware(settings: Settings | None = None) -> Callable:
    """Create middleware for the structured athlete chat agent.

    The athlete workflow intentionally keeps the bounded history loaded by the
    graph's ``load_state`` node. This middleware removes blank message noise,
    applies the loop guard, and appends compact runtime flags prepared by the
    graph.
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
            conversation_id if conversation_id != "unknown" else f"task:{task_id}"
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

        messages = [
            *valid_messages,
            HumanMessage(content=_build_runtime_context(state)),
        ]
        manifest = _string_value(state.get("conversation_file_manifest"))
        if manifest:
            messages.append(HumanMessage(content=manifest))
        return await handler(request.override(messages=messages))

    return athlete_chat_context


def _filter_blank_messages(
    messages: Sequence[BaseMessage],
) -> tuple[list[BaseMessage], int]:
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
    topic_labels = _string_list(state.get("topic_labels"))
    risk_labels = _string_list(state.get("risk_labels"))
    attached_file_ids = _string_list(state.get("attached_file_ids"))
    ready_file_ids = _string_list(state.get("conversation_file_ready_file_ids"))

    return "\n".join(
        [
            "## Athlete Chat Runtime Context",
            f"Current question: {question}",
            f"Topic labels: {_csv_or_none(topic_labels)}",
            f"Risk labels: {_csv_or_none(risk_labels)}",
            f"Attached file count: {len(attached_file_ids)}",
            f"Attached file IDs: {_csv_or_none(attached_file_ids)}",
            f"Ready conversation file count: {len(ready_file_ids)}",
            "",
            "### Tool Guidance Reminder",
            (
                "Data tools are optional. Use search tools only when the current "
                "question needs official KB evidence or ready uploaded-file "
                "evidence."
            ),
            (
                "Policy/process claims should use official KB evidence from "
                "search_playbook_knowledgebase, including NIL, compliance, "
                "academic support, team travel, Teamworks, extra-benefit, "
                "transportation, fees, meals, lodging, services, tutoring, "
                "study hall, and absence-letter questions. Search the KB before "
                "finalizing an answer to these official department-support "
                "questions. If no returned source supports the answer, submit "
                'answer_type "unsupported" and direct the athlete to the '
                "athletic department."
            ),
            (
                "If Ready conversation file count is 0, do not call "
                "search_conversation_files. For uploaded-file questions with no "
                "ready files, say the file is not available for search yet and "
                "submit the final structured response."
            ),
            (
                "After a relevant tool result, produce the final structured "
                "response unless the current question clearly needs the other "
                "search tool."
            ),
            (
                "Do not call the same search tool with equivalent arguments twice. "
                "If a search returns no results, no ready files, or unavailable, "
                "stop using that tool and answer unsupported or with the relevant "
                "safety/refusal type."
            ),
        ]
    )


def format_uploaded_file_manifest(
    files: Sequence[dict[str, Any]],
    *,
    max_files: int = MAX_MANIFEST_FILES,
    max_summary_chars: int = MAX_MANIFEST_SUMMARY_CHARS,
) -> str:
    """Format ready uploaded-file summaries for non-evidence orientation."""
    if not files:
        return ""

    displayed_files = list(files[:max_files])
    sections = [
        "## Uploaded File Manifest",
        (
            "These summaries identify available uploaded files. They are "
            "orientation only; use search_conversation_files excerpts as evidence."
        ),
    ]
    for file in displayed_files:
        sections.append(
            "\n".join(
                [
                    f"File: {_string_value(file.get('filename'), 'unknown')}",
                    f"Conversation file ID: {_string_value(file.get('id'), 'unknown')}",
                    f"Chunk count: {_string_value(file.get('chunk_count'), '0')}",
                    "Summary: "
                    + _truncate_summary(file.get("summary"), max_summary_chars),
                ]
            )
        )

    omitted_count = len(files) - len(displayed_files)
    if omitted_count > 0:
        sections.append(f"Additional ready uploaded files omitted: {omitted_count}")

    return "\n\n".join(sections)


def _truncate_summary(value: Any, max_chars: int) -> str:
    summary = _string_value(value)
    if not summary:
        return "unavailable"
    if len(summary) <= max_chars:
        return summary
    return summary[:max_chars].rstrip() + "..."


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


def _csv_or_none(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "none"
