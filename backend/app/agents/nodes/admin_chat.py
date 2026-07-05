"""Node factories for the Playbook admin analytics chat LangGraph."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from app.agents.runtime_context import AdminChatRuntimeContext
from app.agents.states.admin_chat_state import (
    AdminChatReference,
    AdminChatState,
    AdminChatStructuredResponse,
)
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.analytics import DashboardInsight
from app.repositories.admin_chat import (
    AdminChatMessageRepository,
    AdminChatSessionRepository,
)
from app.repositories.analytics import DashboardInsightRepository
from app.repositories.identity import UserRepository
from app.services.admin_analytics import AdminAnalyticsService, format_snapshot_context
from app.services.agent_stream_service import AgentStreamService

logger = structlog.get_logger(__name__)

UNSUPPORTED_ADMIN_CHAT_RESPONSE = (
    "I can only answer questions about anonymized analytics and stored dashboard "
    "insights. Try asking about query volume, topics, risks, unanswered "
    "questions, or existing insight records."
)
NO_DATA_ADMIN_CHAT_RESPONSE = (
    "No admin analytics or dashboard insight data is available for this window yet."
)
IDENTITY_REFUSAL_RESPONSE = (
    "I cannot reveal athlete identities. Analytics are anonymized, but I can "
    "break results down by topic, risk, or outcome."
)
ACTION_REFUSAL_RESPONSE = (
    "I can only read analytics and existing dashboard insights from this chat. "
    "Use the relevant admin section for document, role, or insight-run actions."
)
LOOP_GUARD_FALLBACK_RESPONSE = "I could not generate an answer in time. Please try asking a narrower analytics question."

IDENTITY_RE = re.compile(
    r"\b("
    r"who\s+(asked|is|was)|which\s+athlete|athlete\s+id|owner|identity|"
    r"athlete\s+name|student\s+name|user\s+name|real\s+name|their\s+names|"
    r"email|provider\s+subject|sport\s+team"
    r")\b",
    re.IGNORECASE,
)
ACTION_RE = re.compile(
    r"\b("
    r"change\s+role|promote|demote|upload|delete|remove|edit|archive|"
    r"run\s+(an?\s+)?insight|trigger\s+(an?\s+)?insight|retry\s+(an?\s+)?insight"
    r")\b",
    re.IGNORECASE,
)


def create_admin_chat_nodes(*, chains: dict[str, Any]) -> dict[str, Any]:
    """Create all nodes needed by the admin chat graph."""

    async def load_session(
        state: AdminChatState,
        runtime: Runtime[AdminChatRuntimeContext],
    ) -> dict[str, Any]:
        """Re-authorize the admin and load bounded session history."""
        context = runtime.context
        session_repo = AdminChatSessionRepository(context.session)
        message_repo = AdminChatMessageRepository(context.session)
        user_repo = UserRepository(context.session)
        task_id = state["task_id"]
        session_id = UUID(state["session_id"])
        admin_user_id = UUID(state["admin_user_id"])
        user_message_id = UUID(state["user_message_id"])
        assistant_message_id = UUID(state["assistant_message_id"])
        organization_id = UUID(state["organization_id"])

        await context.stream_service.publish_progress(
            task_id,
            status="loading_context",
            metadata={"session_id": str(session_id)},
        )

        admin = await user_repo.get(admin_user_id)
        if (
            admin is None
            or not admin.is_active
            or admin.organization_id != organization_id
            or admin.role not in {"admin", "super_admin"}
        ):
            raise ForbiddenError("Admin chat task is not authorized")

        chat_session = await session_repo.get_for_admin(
            session_id=session_id,
            organization_id=organization_id,
            admin_user_id=admin_user_id,
        )
        if chat_session is None:
            raise NotFoundError("Admin chat session", str(session_id))

        user_message = await message_repo.get(user_message_id)
        assistant_message = await message_repo.get(assistant_message_id)
        if (
            user_message is None
            or user_message.session_id != chat_session.id
            or user_message.role != "user"
        ):
            raise NotFoundError("Admin chat user message", str(user_message_id))
        if (
            assistant_message is None
            or assistant_message.session_id != chat_session.id
            or assistant_message.role != "assistant"
            or assistant_message.message_metadata.get("task_id") != task_id
            or assistant_message.message_metadata.get("user_message_id")
            != str(user_message_id)
        ):
            raise NotFoundError(
                "Admin chat assistant message",
                str(assistant_message_id),
            )

        rows = await message_repo.list_recent_history(
            session_id,
            limit=context.settings.ADMIN_CHAT_HISTORY_LIMIT,
        )
        messages: list[RemoveMessage | HumanMessage | AIMessage] = [
            RemoveMessage(id=REMOVE_ALL_MESSAGES)
        ]
        for row in rows:
            if row.role == "user":
                messages.append(HumanMessage(content=row.content, id=str(row.id)))
            elif row.role == "assistant" and row.content:
                messages.append(AIMessage(content=row.content, id=str(row.id)))

        logger.info(
            "admin_chat_session_loaded",
            task_id=task_id,
            session_id=str(session_id),
            history_count=len(messages) - 1,
        )
        return {
            "messages": messages,
            "question": user_message.content,
        }

    async def build_context(
        state: AdminChatState,
        runtime: Runtime[AdminChatRuntimeContext],
    ) -> dict[str, Any]:
        """Build sanitized analytics and insight context for the response."""
        context = runtime.context
        task_id = state["task_id"]
        organization_id = UUID(state["organization_id"])
        window_start = datetime.fromisoformat(state["window_start"])
        window_end = datetime.fromisoformat(state["window_end"])

        await context.stream_service.publish_progress(
            task_id,
            status="building_context",
            metadata={"session_id": state["session_id"]},
        )
        analytics_service = AdminAnalyticsService(
            context.session,
            settings=context.settings,
        )
        snapshot = await analytics_service.build_snapshot(
            organization_id=organization_id,
            window_start=window_start,
            window_end=window_end,
            max_queries=context.settings.ADMIN_CHAT_MAX_QUERY_EXAMPLES,
        )
        insight_repo = DashboardInsightRepository(context.session)
        insights = await insight_repo.list_completed_for_window(
            organization_id=organization_id,
            window_start=window_start,
            window_end=window_end,
            limit=context.settings.ADMIN_CHAT_MAX_DASHBOARD_INSIGHTS,
        )
        context.analytics_snapshot = snapshot
        context.dashboard_insights = insights
        allowed_references = _allowed_references(snapshot=snapshot, insights=insights)
        context.allowed_references = allowed_references
        snapshot_context = format_snapshot_context(snapshot)
        return {
            "snapshot_context": snapshot_context,
            "dashboard_insight_context": _format_dashboard_insight_context(insights),
            "allowed_references": allowed_references,
        }

    async def scope_check(
        state: AdminChatState,
        runtime: Runtime[AdminChatRuntimeContext],
    ) -> dict[str, Any]:
        """Deterministically refuse identity and action-taking requests."""
        question = state.get("question", "")
        task_id = state["task_id"]
        await runtime.context.stream_service.publish_progress(
            task_id,
            status="checking_scope",
            metadata={"session_id": state["session_id"]},
        )
        if IDENTITY_RE.search(question):
            return {
                "should_bypass_agent": True,
                "answer": IDENTITY_REFUSAL_RESPONSE,
                "answer_type": "refusal",
                "references": [],
            }
        if ACTION_RE.search(question):
            return {
                "should_bypass_agent": True,
                "answer": ACTION_REFUSAL_RESPONSE,
                "answer_type": "refusal",
                "references": [],
            }
        return {"should_bypass_agent": False}

    async def run_agent(
        state: AdminChatState,
        runtime: Runtime[AdminChatRuntimeContext],
    ) -> dict[str, Any]:
        """Invoke the structured admin chat agent."""
        context = runtime.context
        task_id = state["task_id"]
        snapshot = context.analytics_snapshot
        if (
            snapshot is not None
            and snapshot.summary.query_volume == 0
            and not context.dashboard_insights
        ):
            return {
                "answer": NO_DATA_ADMIN_CHAT_RESPONSE,
                "answer_type": "unsupported",
                "references": [],
            }

        await context.stream_service.publish_progress(task_id, status="running_agent")
        try:
            result = await chains["admin_chat"].ainvoke(
                {
                    "messages": state["messages"],
                    "task_id": task_id,
                    "session_id": state["session_id"],
                    "organization_id": state["organization_id"],
                    "window_start": state["window_start"],
                    "window_end": state["window_end"],
                    "question": state.get("question", ""),
                    "snapshot_context": state.get("snapshot_context", ""),
                    "dashboard_insight_context": state.get(
                        "dashboard_insight_context",
                        "",
                    ),
                    "allowed_references": state.get("allowed_references", []),
                },
                config=_agent_chain_config(state),
                context=context,
            )
        except ValidationError as exc:
            if not _is_admin_chat_loop_guard(exc):
                raise
            logger.warning(
                "admin_chat_agent_loop_guard_fallback",
                task_id=task_id,
                session_id=state["session_id"],
                message_count=exc.details.get("message_count"),
                max_messages=exc.details.get("max_messages"),
                tool_names=exc.details.get("tool_names", []),
                repeated_tool_call_count=exc.details.get(
                    "repeated_tool_call_count",
                ),
                ai_tool_call_count=exc.details.get("ai_tool_call_count"),
                tool_message_count=exc.details.get("tool_message_count"),
            )
            return {
                "answer": LOOP_GUARD_FALLBACK_RESPONSE,
                "answer_type": "unsupported",
                "references": [],
            }
        structured = _structured_response(result)
        return {
            "answer": structured.answer.strip(),
            "answer_type": structured.answer_type,
            "references": [
                reference.model_dump() for reference in structured.references
            ],
        }

    async def save_response(
        state: AdminChatState,
        runtime: Runtime[AdminChatRuntimeContext],
    ) -> dict[str, Any]:
        """Persist final assistant response and terminal stream events."""
        context = runtime.context
        message_repo = AdminChatMessageRepository(context.session)
        task_id = state["task_id"]
        assistant_message_id = UUID(state["assistant_message_id"])
        await context.stream_service.publish_progress(
            task_id,
            status="persisting_response",
        )

        assistant_message = await message_repo.get(assistant_message_id)
        if assistant_message is None:
            raise NotFoundError(
                "Admin chat assistant message", str(assistant_message_id)
            )

        answer = state.get("answer", "").strip()
        answer_type = state.get("answer_type", "unsupported")
        if answer_type not in {"analytics_answer", "refusal", "unsupported"}:
            answer_type = "unsupported"
        if not answer:
            answer = UNSUPPORTED_ADMIN_CHAT_RESPONSE
            answer_type = "unsupported"

        references = _filter_references(
            state.get("references", []),
            state.get("allowed_references", []),
            max_references=context.settings.ADMIN_CHAT_MAX_REFERENCES,
        )
        if answer_type == "analytics_answer" and not references:
            references = _filter_references(
                [{"type": "metric", "id": "analytics.summary"}],
                state.get("allowed_references", []),
                max_references=context.settings.ADMIN_CHAT_MAX_REFERENCES,
            )

        await context.stream_service.publish_progress(
            task_id,
            status="streaming_response",
        )
        streamed_answer = await _publish_answer_chunks(
            context.stream_service,
            task_id=task_id,
            answer=answer,
        )
        metadata = {
            **assistant_message.message_metadata,
            "task_id": task_id,
            "answer_type": answer_type,
            "model": context.settings.LLM_CHAT_MODEL,
            "window_start": state["window_start"],
            "window_end": state["window_end"],
            "reference_count": len(references),
        }
        await message_repo.update_status_content_references(
            assistant_message,
            status="complete",
            content=streamed_answer,
            references=references,
            metadata=metadata,
        )
        await context.session.commit()

        completion_result = {
            "status": "complete",
            "task_id": task_id,
            "session_id": state["session_id"],
            "assistant_message_id": str(assistant_message.id),
            "answer_type": answer_type,
            "references": references,
            "answer": streamed_answer,
        }
        return {"completion_result": completion_result}

    return {
        "load_session": load_session,
        "build_context": build_context,
        "scope_check": scope_check,
        "run_agent": run_agent,
        "save_response": save_response,
    }


def _agent_chain_config(state: AdminChatState) -> dict[str, object]:
    return {
        "configurable": {
            "task_id": state["task_id"],
            "session_id": state["session_id"],
            "organization_id": state["organization_id"],
        }
    }


def _structured_response(result: Any) -> AdminChatStructuredResponse:
    if isinstance(result, AdminChatStructuredResponse):
        return result
    if isinstance(result, dict):
        structured = result.get("structured_response", result)
        return AdminChatStructuredResponse.model_validate(structured)
    return AdminChatStructuredResponse.model_validate(result)


def _is_admin_chat_loop_guard(exc: ValidationError) -> bool:
    return (
        exc.details.get("phase") == "admin_chat"
        and "message_count" in exc.details
        and "max_messages" in exc.details
    )


async def _publish_answer_chunks(
    stream_service: AgentStreamService,
    *,
    task_id: str,
    answer: str,
) -> str:
    """Publish validated answer text as ordered chunks and return exact text."""
    streamed_parts: list[str] = []
    for chunk in _answer_chunks(answer):
        await stream_service.publish_chunk(task_id, content=chunk)
        streamed_parts.append(chunk)
    return "".join(streamed_parts)


def _answer_chunks(answer: str) -> list[str]:
    """Split final text into word-like chunks while preserving whitespace."""
    chunks = [match.group(0) for match in re.finditer(r"\S+\s*", answer)]
    return chunks or ([answer] if answer else [])


def _allowed_references(
    *, snapshot: Any, insights: list[DashboardInsight]
) -> list[dict[str, str]]:
    allowed: list[dict[str, str]] = [{"type": "metric", "id": "analytics.summary"}]
    for query in getattr(snapshot, "queries", []):
        message_id = getattr(query, "display_message_id", None) or getattr(
            query,
            "message_id",
            None,
        )
        if message_id is not None:
            allowed.append({"type": "query", "id": str(message_id)})
    for insight in insights:
        allowed.append({"type": "dashboard_insight", "id": str(insight.id)})
    return allowed


def _filter_references(
    candidate_references: list[Any],
    allowed_references: list[dict[str, str]],
    *,
    max_references: int,
) -> list[dict[str, str]]:
    allowed = {_reference_key(reference) for reference in allowed_references}
    seen: set[str] = set()
    valid: list[dict[str, str]] = []
    for candidate in candidate_references:
        reference = _reference_dict(candidate)
        if reference is None:
            continue
        key = _reference_key(reference)
        if key not in allowed or key in seen:
            continue
        seen.add(key)
        valid.append(reference)
        if len(valid) >= max_references:
            break
    return valid


def _reference_dict(value: Any) -> dict[str, str] | None:
    if isinstance(value, AdminChatReference):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None
    reference_type = str(value.get("type") or "").strip()
    reference_id = str(value.get("id") or "").strip()
    if reference_type not in {"metric", "dashboard_insight", "query"}:
        return None
    if not reference_id:
        return None
    return {"type": reference_type, "id": reference_id}


def _reference_key(reference: dict[str, str]) -> str:
    return f"{reference.get('type')}:{reference.get('id')}"


def _format_dashboard_insight_context(insights: list[DashboardInsight]) -> str:
    if not insights:
        return "## Completed Dashboard Insights\nNo completed dashboard insights overlap this window."
    lines = ["## Completed Dashboard Insights"]
    for insight in insights:
        lines.append(
            "\n".join(
                [
                    f"Insight ID: {insight.id}",
                    f"Summary: {insight.summary}",
                    "Headline cards: " + _compact_jsonish(insight.headline_cards),
                    "Topic breakdown: " + _compact_jsonish(insight.topic_breakdown),
                    "Unanswered questions: "
                    + _compact_jsonish(insight.unanswered_questions),
                    "Risk breakdown: " + _compact_jsonish(insight.risk_breakdown),
                    "Recommended attention areas: "
                    + _compact_jsonish(insight.recommended_attention_areas),
                    f"Generated at: {insight.generated_at.isoformat()}",
                ]
            )
        )
    return "\n\n".join(lines)


def _compact_jsonish(value: Any) -> str:
    text = str(value)
    if len(text) <= 500:
        return text
    return text[:497] + "..."
