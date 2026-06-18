"""DTO mappers for backend KB document services."""

from __future__ import annotations

from app.models.knowledge_base import KBDocument, KBDocumentEvent
from app.schemas.kb_documents import KBDocumentEventResponse, KBDocumentResponse


def kb_document_to_response(document: KBDocument) -> KBDocumentResponse:
    """Map a KB document ORM object to a public DTO."""
    return KBDocumentResponse.model_validate(document)


def kb_event_to_response(event: KBDocumentEvent) -> KBDocumentEventResponse:
    """Map a KB document event ORM object to a public DTO."""
    return KBDocumentEventResponse(
        id=event.id,
        document_id=event.document_id,
        event_type=event.event_type,
        status=event.status,
        message=event.message,
        metadata=event.event_metadata,
        created_at=event.created_at,
    )
