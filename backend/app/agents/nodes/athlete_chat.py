"""Node factories for the Playbook athlete chat LangGraph."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from app.agents.context.middleware.athlete_chat_middleware import (
    format_uploaded_file_manifest,
)
from app.agents.guardrails.safety import evaluate_athlete_message_safety
from app.agents.runtime_context import AthleteChatRuntimeContext
from app.agents.states.athlete_chat_state import (
    AthleteChatState,
    AthleteChatStructuredResponse,
)
from app.agents.tools.knowledgebase import (
    KnowledgebaseSource,
    SourceRegistry,
    conversation_file_search_context,
)
from app.core.exceptions import NotFoundError
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
) -> dict[str, Any]:
    """Create all nodes needed by the athlete chat graph."""
    async def load_state(
        state: AthleteChatState,
        runtime: Runtime[AthleteChatRuntimeContext],
    ) -> dict[str, Any]:
        """Validate task ownership and load bounded conversation history."""
        context = runtime.context
        conversation_repo = ConversationRepository(context.session)
        message_repo = ConversationMessageRepository(context.session)
        task_id = state["task_id"]
        conversation_id = UUID(state["conversation_id"])
        athlete_user_id = UUID(state["athlete_user_id"])
        user_message_id = UUID(state["user_message_id"])
        assistant_message_id = UUID(state["assistant_message_id"])
        organization_id = UUID(state["organization_id"])

        await context.stream_service.publish_progress(
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
            limit=context.settings.ATHLETE_CHAT_HISTORY_LIMIT,
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

    async def safety_check(
        state: AthleteChatState,
        runtime: Runtime[AthleteChatRuntimeContext],
    ) -> dict[str, Any]:
        """Run deterministic pre-generation safety and topic labeling."""
        context = runtime.context
        task_id = state["task_id"]
        await context.stream_service.publish_progress(
            task_id,
            status="checking_safety",
            metadata={"assistant_message_id": state["assistant_message_id"]},
        )
        decision = evaluate_athlete_message_safety(state["user_message_content"])
        if decision.bypass_agent:
            return {
                "should_bypass_agent": True,
                "answer": decision.response_text,
                "answer_type": decision.answer_type,
                "cited_source_keys": [],
                "safety_outcome": decision.safety_outcome,
            }

        return {
            "should_bypass_agent": False,
            "answer_type": decision.answer_type,
            "cited_source_keys": [],
            "safety_outcome": decision.safety_outcome,
        }

    async def prepare_conversation_file_scope(
        state: AthleteChatState,
        runtime: Runtime[AthleteChatRuntimeContext],
    ) -> dict[str, Any]:
        """Prepare trusted private conversation-file IDs for the search tool."""
        if state.get("should_bypass_agent", False):
            return _empty_conversation_file_scope()

        context = runtime.context
        file_repo = ConversationFileRepository(context.session)
        task_id = state["task_id"]
        conversation_id = UUID(state["conversation_id"])
        attached_file_ids = _uuid_list(state.get("attached_file_ids", []))
        await context.stream_service.publish_progress(
            task_id,
            status="preparing_file_scope",
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
            return _empty_conversation_file_scope()
        manifest = format_uploaded_file_manifest(
            [
                {
                    "id": str(file.id),
                    "filename": file.filename,
                    "chunk_count": file.chunk_count,
                    "summary": file.summary,
                }
                for file in ready_files
            ]
        )
        logger.info(
            "athlete_chat_conversation_file_scope_loaded",
            task_id=task_id,
            conversation_id=str(conversation_id),
            ready_file_count=len(ready_file_ids),
            manifest_file_count=min(len(ready_files), 8),
        )
        return {
            "conversation_file_ready_file_ids": [
                str(file_id) for file_id in ready_file_ids
            ],
            "conversation_file_manifest": manifest,
        }

    async def run_agent(
        state: AthleteChatState,
        runtime: Runtime[AthleteChatRuntimeContext],
    ) -> dict[str, Any]:
        """Invoke the structured athlete chat agent."""
        context = runtime.context
        task_id = state["task_id"]
        await context.stream_service.publish_progress(task_id, status="running_agent")
        with conversation_file_search_context(
            organization_id=state["organization_id"],
            conversation_id=state["conversation_id"],
            file_ids=state.get("conversation_file_ready_file_ids", []),
        ):
            result = await chains["athlete_chat"].ainvoke(
                {
                    "messages": state["messages"],
                    "task_id": task_id,
                    "conversation_id": state["conversation_id"],
                    "user_message_content": state.get("user_message_content", ""),
                    "attached_file_ids": state.get("attached_file_ids", []),
                    "conversation_file_ready_file_ids": state.get(
                        "conversation_file_ready_file_ids",
                        [],
                    ),
                    "conversation_file_manifest": state.get(
                        "conversation_file_manifest",
                        "",
                    ),
                    "topic_labels": state.get("topic_labels", []),
                    "risk_labels": state.get("risk_labels", []),
                },
                config=_agent_chain_config(state),
                context=context,
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

    async def save_state(
        state: AthleteChatState,
        runtime: Runtime[AthleteChatRuntimeContext],
    ) -> dict[str, Any]:
        """Persist final assistant response, citations, and terminal stream event."""
        context = runtime.context
        message_repo = ConversationMessageRepository(context.session)
        citation_repo = MessageCitationRepository(context.session)
        task_id = state["task_id"]
        assistant_message_id = UUID(state["assistant_message_id"])
        await context.stream_service.publish_progress(
            task_id,
            status="persisting_response",
        )

        assistant_message = await message_repo.get(assistant_message_id)
        if assistant_message is None:
            raise NotFoundError("Assistant message", str(assistant_message_id))

        cited_sources = _sources_for_keys(
            state.get("cited_source_keys", []),
            context.source_registry,
        )
        answer = state.get("answer", "").strip()
        answer_type = state.get("answer_type", "grounded_answer")
        if not answer:
            answer = UNSUPPORTED_RESPONSE
            answer_type = "unsupported"

        limited_sources = cited_sources[: context.settings.ATHLETE_CHAT_MAX_CITATIONS]
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
            "source_keys": [source.source_key for source in limited_sources],
            "kb_zero_hit": bool(
                not state.get("should_bypass_agent", False)
                and not context.source_registry
            ),
            "model": context.settings.LLM_CHAT_MODEL,
        }
        await message_repo.update_status_and_content(
            assistant_message,
            status="complete",
            content=streamed_answer,
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
        await context.session.commit()

        completion_result = {
            "status": "complete",
            "task_id": task_id,
            "assistant_message_id": str(assistant_message.id),
            "answer_type": answer_type,
            "citation_count": len(limited_sources),
            "answer": streamed_answer,
        }
        return {"completion_result": completion_result}

    return {
        "load_state": load_state,
        "safety_check": safety_check,
        "prepare_conversation_file_scope": prepare_conversation_file_scope,
        "run_agent": run_agent,
        "save_state": save_state,
    }


def _agent_chain_config(state: AthleteChatState) -> dict[str, object]:
    return {
        "configurable": {
            "task_id": state["task_id"],
            "conversation_id": state["conversation_id"],
            "organization_id": state["organization_id"],
            "conversation_file_ready_file_ids": state.get(
                "conversation_file_ready_file_ids",
                [],
            ),
        }
    }


def _structured_response(result: Any) -> AthleteChatStructuredResponse:
    if isinstance(result, AthleteChatStructuredResponse):
        return result
    if isinstance(result, dict):
        structured = result.get("structured_response", result)
        return AthleteChatStructuredResponse.model_validate(structured)
    return AthleteChatStructuredResponse.model_validate(result)


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


def _empty_conversation_file_scope() -> dict[str, object]:
    return {
        "conversation_file_ready_file_ids": [],
        "conversation_file_manifest": "",
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
