"""DTO mappers for athlete conversation services."""

from __future__ import annotations

from app.models.conversations import (
    Conversation,
    ConversationFile,
    ConversationMessage,
    MessageCitation,
)
from app.schemas.conversations import (
    ConversationDetailResponse,
    ConversationFileSummaryResponse,
    ConversationMessageResponse,
    ConversationSummaryResponse,
    MessageCitationResponse,
)


def conversation_summary_response(
    conversation: Conversation,
) -> ConversationSummaryResponse:
    """Map a conversation ORM object to a public summary DTO."""
    return ConversationSummaryResponse.model_validate(conversation)


def conversation_detail_response(
    conversation: Conversation,
    *,
    messages: list[ConversationMessageResponse],
    files: list[ConversationFileSummaryResponse],
) -> ConversationDetailResponse:
    """Map a conversation and nested DTOs to a public detail DTO."""
    return ConversationDetailResponse(
        **conversation_summary_response(conversation).model_dump(),
        messages=messages,
        files=files,
    )


def conversation_message_response(
    message: ConversationMessage,
    *,
    citations: list[MessageCitation],
) -> ConversationMessageResponse:
    """Map a conversation message ORM object to a public DTO."""
    return ConversationMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        status=message.status,
        safety_outcome=message.safety_outcome,
        topic_labels=message.topic_labels,
        risk_labels=message.risk_labels,
        metadata=message.message_metadata,
        citations=[message_citation_response(citation) for citation in citations],
        created_at=message.created_at,
    )


def message_citation_response(citation: MessageCitation) -> MessageCitationResponse:
    """Map a message citation ORM object to a public DTO."""
    return MessageCitationResponse(
        id=citation.id,
        message_id=citation.message_id,
        document_id=citation.document_id,
        chunk_id=citation.chunk_id,
        source_title=citation.source_title,
        source_metadata=citation.source_metadata,
        rank=citation.rank,
        created_at=citation.created_at,
    )


def conversation_file_response(
    file: ConversationFile,
    chunk_count: int,
) -> ConversationFileSummaryResponse:
    """Map a conversation file ORM object to a safe public DTO."""
    return ConversationFileSummaryResponse(
        id=file.id,
        conversation_id=file.conversation_id,
        message_id=file.message_id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        extraction_status=file.extraction_status,
        chunk_count=chunk_count,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )
