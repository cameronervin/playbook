"""Ingestion metadata normalization helpers."""

from __future__ import annotations

import uuid
from typing import Any, TypeAlias

from fastapi import HTTPException, status

from app.schemas.ingest import IngestConversationFileRequest, IngestDocumentRequest

IngestRequest: TypeAlias = IngestDocumentRequest | IngestConversationFileRequest


def metadata_with_organization(
    metadata: dict[str, Any] | None,
    *,
    organization_id: uuid.UUID,
) -> dict[str, Any]:
    """Return metadata stamped with the trusted top-level organization scope."""
    normalized = dict(metadata or {})
    requested_value = str(organization_id)
    existing_value = normalized.get("organization_id")
    if existing_value not in (None, requested_value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metadata.organization_id must match organization_id",
        )
    normalized["organization_id"] = requested_value
    return normalized


def metadata_from_ingest_request(req: IngestRequest) -> dict[str, Any]:
    if (
        isinstance(req, IngestConversationFileRequest)
        and req.visibility_policy.get("scope") != "conversation"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                'visibility_policy.scope must be "conversation" for '
                "conversation_file ingestion"
            ),
        )

    metadata: dict[str, Any] = {
        **req.metadata_tags,
        "source_type": req.source_type,
        "organization_id": str(req.organization_id),
        "source_title": req.source_title,
        "visibility_policy": req.visibility_policy,
        "metadata_tags": req.metadata_tags,
        "content_type": req.content_type,
        "size_bytes": req.size_bytes,
        "status_webhook_url": req.status_webhook_url,
        "webhook_enabled": bool(req.status_webhook_url),
    }
    if isinstance(req, IngestDocumentRequest):
        metadata.update(
            {
                "playbook_document_id": str(req.playbook_document_id),
                "source_date": req.source_date.isoformat()
                if req.source_date
                else None,
                "is_official": True,
                "priority": 0,
            }
        )
    else:
        metadata.update(
            {
                "conversation_id": str(req.conversation_id),
                "conversation_file_id": str(req.conversation_file_id),
            }
        )
    return metadata_with_organization(metadata, organization_id=req.organization_id)
