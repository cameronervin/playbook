"""DTO mapper tests for conversation services."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.conversations import (
    Conversation,
    ConversationFile,
    ConversationMessage,
    MessageCitation,
)
from app.services.conversations.mappers import (
    conversation_detail_response,
    conversation_file_response,
    conversation_message_response,
)


def test_conversation_message_response_maps_citations_explicitly() -> None:
    message_id = uuid4()
    citation_id = uuid4()
    created_at = datetime(2026, 6, 18, tzinfo=UTC)
    message = ConversationMessage(
        id=message_id,
        conversation_id=uuid4(),
        role="assistant",
        content="Use the official policy.",
        status="complete",
        safety_outcome=None,
        topic_labels=["nil"],
        risk_labels=["compliance"],
        message_metadata={"answer_type": "grounded_answer"},
        created_at=created_at,
    )
    citation = MessageCitation(
        id=citation_id,
        message_id=message_id,
        document_id=uuid4(),
        chunk_id=uuid4(),
        source_title="NIL Policy",
        source_metadata={"source_date": "2026-01-01"},
        rank=1,
        created_at=created_at,
    )

    response = conversation_message_response(message, citations=[citation])

    assert response.id == message_id
    assert response.metadata == {"answer_type": "grounded_answer"}
    assert response.citations[0].id == citation_id


def test_conversation_file_response_excludes_private_storage_fields() -> None:
    file = ConversationFile(
        id=uuid4(),
        conversation_id=uuid4(),
        message_id=None,
        uploaded_by=uuid4(),
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=1234,
        storage_key="conversation-files/originals/private.pdf",
        extraction_status="ready",
        kb_service_document_id=uuid4(),
        summary="Internal summary",
        chunk_count=3,
        extracted_text_ref="private/ref",
        extracted_text_sha256="abc123",
        extracted_char_count=99,
        extraction_metadata={"source_uri": "https://signed.example"},
        error_message=None,
        created_at=datetime(2026, 6, 18, tzinfo=UTC),
        updated_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    response = conversation_file_response(file, file.chunk_count)
    dumped = response.model_dump()

    assert dumped == {
        "id": file.id,
        "conversation_id": file.conversation_id,
        "message_id": None,
        "filename": "contract.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1234,
        "extraction_status": "ready",
        "chunk_count": 3,
        "created_at": file.created_at,
        "updated_at": file.updated_at,
    }


def test_conversation_detail_response_uses_safe_nested_dtos() -> None:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    conversation = Conversation(
        id=uuid4(),
        organization_id=uuid4(),
        athlete_id=uuid4(),
        title=None,
        status="active",
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )
    message = ConversationMessage(
        id=uuid4(),
        conversation_id=conversation.id,
        role="user",
        content="Can I accept this?",
        status="complete",
        safety_outcome=None,
        topic_labels=[],
        risk_labels=[],
        message_metadata={},
        created_at=now,
    )
    file = ConversationFile(
        id=uuid4(),
        conversation_id=conversation.id,
        message_id=None,
        uploaded_by=conversation.athlete_id,
        filename="deal.pdf",
        content_type="application/pdf",
        size_bytes=42,
        storage_key="private/key",
        extraction_status="uploaded",
        chunk_count=0,
        extraction_metadata={},
        created_at=now,
        updated_at=now,
    )

    response = conversation_detail_response(
        conversation,
        messages=[conversation_message_response(message, citations=[])],
        files=[conversation_file_response(file, 0)],
    )

    assert response.id == conversation.id
    assert response.messages[0].content == "Can I accept this?"
    assert response.files[0].filename == "deal.pdf"
