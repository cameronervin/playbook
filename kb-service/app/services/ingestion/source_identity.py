"""Trusted source identity and content-dedupe helpers for ingestion."""

from __future__ import annotations

import hashlib
from typing import Any

from app.repositories.document_repo import DocumentRepository
from app.schemas.ingest import IngestDocumentRequest
from app.services.ingestion.metadata import IngestRequest

SOURCE_IDENTITY_CONFLICT_DETAIL = (
    "document content already exists for a different trusted source identity"
)


def dedupe_md5_for_ingest_request(req: IngestRequest, raw_md5: str) -> str:
    """Return the current kb.documents md5 value for this request.

    Admin uploads keep the raw content MD5 for backward compatibility.
    Conversation files scope the hash to trusted private identifiers so the
    existing unique constraint cannot collapse private uploads into shared docs.
    """
    if isinstance(req, IngestDocumentRequest):
        return raw_md5
    scoped_value = (
        f"{req.source_type}:{req.organization_id}:{req.conversation_id}:"
        f"{req.conversation_file_id}:{raw_md5}"
    )
    return hashlib.md5(scoped_value.encode()).hexdigest()  # noqa: S324


def metadata_matches_trusted_source_identity(
    metadata: dict[str, Any] | None,
    req: IngestRequest,
) -> bool:
    metadata = metadata or {}
    if metadata.get("source_type") != req.source_type:
        return False
    if metadata.get("organization_id") != str(req.organization_id):
        return False
    if isinstance(req, IngestDocumentRequest):
        return metadata.get("playbook_document_id") == str(req.playbook_document_id)
    return (
        metadata.get("conversation_id") == str(req.conversation_id)
        and metadata.get("conversation_file_id") == str(req.conversation_file_id)
        and metadata.get("visibility_policy") == {"scope": "conversation"}
    )


class SourceIdentityResolver:
    """Resolve existing documents by trusted request identity."""

    def __init__(self, document_repo: DocumentRepository) -> None:
        self._document_repo = document_repo

    async def get_existing_document(self, req: IngestRequest) -> Any | None:
        if isinstance(req, IngestDocumentRequest):
            return await self._document_repo.get_by_admin_source_identity(
                configuration_id=req.configuration_id,
                organization_id=req.organization_id,
                playbook_document_id=req.playbook_document_id,
            )
        return await self._document_repo.get_by_conversation_file_source_identity(
            configuration_id=req.configuration_id,
            organization_id=req.organization_id,
            conversation_id=req.conversation_id,
            conversation_file_id=req.conversation_file_id,
        )
