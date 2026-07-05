"""DTO mappers for backend KB document services."""

from __future__ import annotations

from app.models.knowledge_base import KBDocument, KBDocumentEvent
from app.schemas.kb_documents import KBDocumentEventResponse, KBDocumentResponse


def kb_document_to_response(document: KBDocument) -> KBDocumentResponse:
    """Map a KB document ORM object to a public DTO."""
    tag_slugs = [link.tag.slug for link in document.tag_links]
    if not tag_slugs and isinstance(document.metadata_tags.get("tag_slugs"), list):
        tag_slugs = [
            slug
            for slug in document.metadata_tags["tag_slugs"]
            if isinstance(slug, str)
        ]
    return KBDocumentResponse(
        id=document.id,
        organization_id=document.organization_id,
        uploaded_by=document.uploaded_by,
        title=document.title,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        processing_status=document.processing_status,  # type: ignore[arg-type]
        failure_reason=document.failure_reason,
        collection_id=document.collection_id,
        tag_slugs=tag_slugs,
        visibility_policy=document.visibility_policy,
        metadata_tags=document.metadata_tags,
        source_date=document.source_date,
        kb_service_document_id=document.kb_service_document_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


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
