"""Node factories for the Playbook athlete chat LangGraph."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context.token_budget import truncate_to_token_budget
from app.agents.guardrails.safety import evaluate_athlete_message_safety
from app.agents.states.athlete_chat_state import (
    AthleteChatState,
    AthleteChatStructuredResponse,
)
from app.agents.tools.knowledgebase import (
    KnowledgebaseSource,
    SourceRegistry,
    format_conversation_file_context,
    knowledgebase_organization_context,
    register_knowledgebase_sources,
)
from app.core.config import Settings
from app.core.exceptions import KnowledgebaseError, NotFoundError
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.services.agent_stream_service import AgentStreamService

logger = structlog.get_logger(__name__)

UNSUPPORTED_RESPONSE = (
    "I don't have enough official Playbook guidance to answer that safely. "
    "Please contact the athletic department for the current policy or next step."
)


def create_athlete_chat_nodes(
    *,
    chains: dict[str, Any],
    session: AsyncSession,
    settings: Settings,
    stream_service: AgentStreamService,
    source_registry: SourceRegistry,
    knowledgebase_provider: BaseKnowledgebaseProvider,
) -> dict[str, Any]:
    """Create all nodes needed by the athlete chat graph."""
    conversation_repo = ConversationRepository(session)
    message_repo = ConversationMessageRepository(session)
    citation_repo = MessageCitationRepository(session)
    file_repo = ConversationFileRepository(session)

    async def load_state(state: AthleteChatState) -> dict[str, Any]:
        """Validate task ownership and load bounded conversation history."""
        task_id = state["task_id"]
        conversation_id = UUID(state["conversation_id"])
        athlete_user_id = UUID(state["athlete_user_id"])
        user_message_id = UUID(state["user_message_id"])
        assistant_message_id = UUID(state["assistant_message_id"])
        organization_id = UUID(state["organization_id"])

        await stream_service.publish_progress(
            task_id,
            status="loading_context",
            metadata={"conversation_id": str(conversation_id)},
        )

        conversation = await conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=organization_id,
            athlete_id=athlete_user_id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        user_message = await message_repo.get(user_message_id)
        assistant_message = await message_repo.get(assistant_message_id)
        if (
            user_message is None
            or user_message.conversation_id != conversation.id
            or user_message.role != "user"
        ):
            raise NotFoundError("User message", str(user_message_id))
        if (
            assistant_message is None
            or assistant_message.conversation_id != conversation.id
            or assistant_message.role != "assistant"
            or assistant_message.message_metadata.get("task_id") != task_id
            or assistant_message.message_metadata.get("user_message_id")
            != str(user_message_id)
        ):
            raise NotFoundError("Assistant message", str(assistant_message_id))

        rows = await message_repo.list_recent_for_conversation(
            conversation_id,
            limit=settings.ATHLETE_CHAT_HISTORY_LIMIT,
        )
        messages: list[RemoveMessage | HumanMessage | AIMessage] = [
            RemoveMessage(id=REMOVE_ALL_MESSAGES)
        ]
        for row in rows:
            if row.role == "user":
                messages.append(HumanMessage(content=row.content, id=str(row.id)))
            elif row.role == "assistant" and row.status == "complete" and row.content:
                messages.append(AIMessage(content=row.content, id=str(row.id)))

        logger.info(
            "athlete_chat_state_loaded",
            task_id=task_id,
            conversation_id=str(conversation_id),
            message_count=len(messages) - 1,
            attached_file_count=len(state.get("attached_file_ids", [])),
        )
        return {
            "messages": messages,
            "user_message_content": user_message.content,
        }

    async def safety_check(state: AthleteChatState) -> dict[str, Any]:
        """Run deterministic pre-generation safety and topic labeling."""
        task_id = state["task_id"]
        await stream_service.publish_progress(
            task_id,
            status="checking_safety",
            metadata={"assistant_message_id": state["assistant_message_id"]},
        )
        decision = evaluate_athlete_message_safety(state["user_message_content"])
        if decision.bypass_agent:
            return {
                "should_bypass_agent": True,
                "requires_kb_support": decision.requires_kb_support,
                "answer": decision.response_text,
                "answer_type": decision.answer_type,
                "cited_source_keys": [],
                "topic_labels": decision.topic_labels,
                "risk_labels": decision.risk_labels,
                "safety_outcome": decision.safety_outcome,
            }

        return {
            "should_bypass_agent": False,
            "requires_kb_support": decision.requires_kb_support,
            "answer_type": decision.answer_type,
            "cited_source_keys": [],
            "topic_labels": decision.topic_labels,
            "risk_labels": decision.risk_labels,
            "safety_outcome": decision.safety_outcome,
        }

    async def prepare_conversation_file_snippets(
        state: AthleteChatState,
    ) -> dict[str, Any]:
        """Prepare trusted private conversation-file snippets for middleware."""
        if state.get("should_bypass_agent", False):
            return _empty_conversation_file_context()

        task_id = state["task_id"]
        conversation_id = UUID(state["conversation_id"])
        organization_id = UUID(state["organization_id"])
        attached_file_ids = _uuid_list(state.get("attached_file_ids", []))
        await stream_service.publish_progress(
            task_id,
            status="retrieving_file_context",
            metadata={
                "conversation_id": str(conversation_id),
                "attached_file_count": len(attached_file_ids),
            },
        )

        if attached_file_ids:
            ready_files = await file_repo.list_ready_by_conversation_and_ids(
                conversation_id,
                attached_file_ids,
            )
        else:
            ready_files = await file_repo.list_ready_by_conversation(conversation_id)
        ready_file_ids = [file.id for file in ready_files]
        if not ready_file_ids:
            return _empty_conversation_file_context()

        try:
            result = await knowledgebase_provider.search_conversation_files(
                query=state.get("user_message_content", ""),
                organization_id=organization_id,
                conversation_id=conversation_id,
                file_ids=ready_file_ids,
                max_docs=settings.KB_MAX_DOCS,
                score_threshold=settings.KB_SCORE_THRESHOLD,
            )
        except KnowledgebaseError as exc:
            logger.warning(
                "athlete_chat_conversation_file_context_unavailable",
                task_id=task_id,
                conversation_id=str(conversation_id),
                error_type=type(exc).__name__,
            )
            return _empty_conversation_file_context()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "athlete_chat_conversation_file_context_error",
                task_id=task_id,
                conversation_id=str(conversation_id),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return _empty_conversation_file_context()

        sources = register_knowledgebase_sources(result, registry=source_registry)
        context = format_conversation_file_context(sources)
        if not context:
            return _empty_conversation_file_context()
        context = truncate_to_token_budget(context, settings.KB_CONTEXT_MAX_TOKENS)
        logger.info(
            "athlete_chat_conversation_file_context_loaded",
            task_id=task_id,
            conversation_id=str(conversation_id),
            ready_file_count=len(ready_file_ids),
            source_count=len(sources),
        )
        return {
            "conversation_file_context": context,
            "conversation_file_source_count": len(sources),
            "conversation_file_ready_file_ids": [
                str(file_id) for file_id in ready_file_ids
            ],
        }

    async def run_agent(state: AthleteChatState) -> dict[str, Any]:
        """Invoke the structured athlete chat agent."""
        task_id = state["task_id"]
        await stream_service.publish_progress(task_id, status="running_agent")
        with knowledgebase_organization_context(state["organization_id"]):
            result = await chains["athlete_chat"].ainvoke(
                {
                    "messages": state["messages"],
                    "task_id": task_id,
                    "conversation_id": state["conversation_id"],
                    "user_message_content": state.get("user_message_content", ""),
                    "attached_file_ids": state.get("attached_file_ids", []),
                    "conversation_file_context": state.get(
                        "conversation_file_context",
                        "",
                    ),
                    "conversation_file_source_count": state.get(
                        "conversation_file_source_count",
                        0,
                    ),
                    "conversation_file_ready_file_ids": state.get(
                        "conversation_file_ready_file_ids",
                        [],
                    ),
                    "requires_kb_support": state.get("requires_kb_support", False),
                    "topic_labels": state.get("topic_labels", []),
                    "risk_labels": state.get("risk_labels", []),
                }
            )
        structured = _structured_response(result)
        return {
            "answer": structured.answer.strip(),
            "answer_type": structured.answer_type,
            "cited_source_keys": structured.cited_source_keys,
            "topic_labels": _merge_labels(
                state.get("topic_labels", []),
                structured.topic_labels,
            ),
            "risk_labels": _merge_labels(
                state.get("risk_labels", []),
                structured.risk_labels,
            ),
            "safety_outcome": structured.safety_outcome,
        }

    async def save_state(state: AthleteChatState) -> dict[str, Any]:
        """Persist final assistant response, citations, and terminal stream event."""
        task_id = state["task_id"]
        assistant_message_id = UUID(state["assistant_message_id"])
        await stream_service.publish_progress(task_id, status="persisting_response")

        assistant_message = await message_repo.get(assistant_message_id)
        if assistant_message is None:
            raise NotFoundError("Assistant message", str(assistant_message_id))

        cited_sources = _sources_for_keys(
            state.get("cited_source_keys", []),
            source_registry,
        )
        answer = state.get("answer", "").strip()
        answer_type = state.get("answer_type", "grounded_answer")
        if state.get("requires_kb_support") and not cited_sources:
            answer = UNSUPPORTED_RESPONSE
            answer_type = "unsupported"
        if not answer:
            answer = UNSUPPORTED_RESPONSE
            answer_type = "unsupported"

        limited_sources = cited_sources[: settings.ATHLETE_CHAT_MAX_CITATIONS]
        metadata = {
            **assistant_message.message_metadata,
            "task_id": task_id,
            "answer_type": answer_type,
            "source_keys": [source.source_key for source in limited_sources],
            "kb_zero_hit": bool(
                not state.get("should_bypass_agent", False) and not source_registry
            ),
            "model": settings.LLM_CHAT_MODEL,
        }
        await message_repo.update_status_and_content(
            assistant_message,
            status="complete",
            content=answer,
            safety_outcome=answer_type,
            topic_labels=state.get("topic_labels", []),
            risk_labels=state.get("risk_labels", []),
            metadata=metadata,
        )
        await citation_repo.delete_by_message(assistant_message.id)
        for rank, source in enumerate(limited_sources, start=1):
            await citation_repo.create(
                message_id=assistant_message.id,
                document_id=_citation_document_id(source),
                chunk_id=_uuid_or_none(source.metadata.get("chunk_id")),
                source_title=source.source_title,
                source_metadata=source.metadata,
                rank=rank,
            )
        await session.commit()

        await stream_service.publish_chunk(task_id, content=answer)
        completion_result = {
            "status": "complete",
            "task_id": task_id,
            "assistant_message_id": str(assistant_message.id),
            "answer_type": answer_type,
            "citation_count": len(limited_sources),
        }
        await stream_service.publish_complete(task_id, data=completion_result)
        return {"completion_result": completion_result}

    return {
        "load_state": load_state,
        "safety_check": safety_check,
        "prepare_conversation_file_snippets": prepare_conversation_file_snippets,
        "run_agent": run_agent,
        "save_state": save_state,
    }


def _structured_response(result: Any) -> AthleteChatStructuredResponse:
    if isinstance(result, AthleteChatStructuredResponse):
        return result
    if isinstance(result, dict):
        structured = result.get("structured_response", result)
        return AthleteChatStructuredResponse.model_validate(structured)
    return AthleteChatStructuredResponse.model_validate(result)


def _sources_for_keys(
    source_keys: Sequence[str],
    source_registry: SourceRegistry,
) -> list[KnowledgebaseSource]:
    seen: set[str] = set()
    sources: list[KnowledgebaseSource] = []
    for raw_key in source_keys:
        source_key = _normalize_source_key(raw_key)
        if source_key in seen:
            continue
        source = source_registry.get(source_key)
        if source is None:
            continue
        seen.add(source_key)
        sources.append(source)
    return sources


def _normalize_source_key(source_key: str) -> str:
    normalized = source_key.strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1].strip()
    return normalized


def _merge_labels(primary: Sequence[str], secondary: Sequence[str]) -> list[str]:
    labels: list[str] = []
    for label in [*primary, *secondary]:
        if label and label not in labels:
            labels.append(label)
    return labels


def _empty_conversation_file_context() -> dict[str, object]:
    return {
        "conversation_file_context": "",
        "conversation_file_source_count": 0,
        "conversation_file_ready_file_ids": [],
    }


def _uuid_list(values: Sequence[str] | None) -> list[UUID]:
    resolved: list[UUID] = []
    for value in values or []:
        try:
            resolved.append(UUID(str(value)))
        except ValueError:
            continue
    return resolved


def _citation_document_id(source: KnowledgebaseSource) -> UUID | None:
    metadata = source.metadata
    if metadata.get("source_type") == "conversation_file":
        return _uuid_or_none(metadata.get("conversation_file_id")) or _uuid_or_none(
            metadata.get("document_id")
        )
    return _uuid_or_none(metadata.get("playbook_document_id")) or _uuid_or_none(
        metadata.get("document_id")
    )


def _uuid_or_none(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None
