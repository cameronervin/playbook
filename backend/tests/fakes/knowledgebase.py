from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID, uuid4

from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBIngestRequest,
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KnowledgebaseResult,
    RetrievedChunk,
)

_SENSITIVE_WEBHOOK_METADATA = {
    "source_uri",
    "presigned_url",
    "signed_url",
    "raw_text",
    "extracted_text",
    "file_contents",
}


class FakeKBDispatchRecorder:
    """Test double that records trusted backend-derived KB ingest requests."""

    def __init__(self) -> None:
        self.requests: list[KBDocumentIngestRequest | KBConversationFileIngestRequest] = []

    async def dispatch(self, request: KBIngestRequest) -> KBDocumentIngestResponse:
        self.requests.append(request)
        if isinstance(request, KBDocumentIngestRequest):
            playbook_document_id = request.playbook_document_id
        else:
            playbook_document_id = request.conversation_file_id
        return KBDocumentIngestResponse(
            kb_service_document_id=uuid4(),
            playbook_document_id=playbook_document_id,
            task_id=f"fake-kb-{len(self.requests)}",
            status="pending",
        )


class FakeScopedRetrievalProvider:
    """In-memory retrieval fake that enforces source-type privacy filters."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        *,
        max_docs: int = 10,
        score_threshold: float = 0.0,
        metadata_filter: dict[str, Any] | None = None,
    ) -> KnowledgebaseResult:
        metadata_filter = metadata_filter or {}
        results = [
            chunk
            for chunk in self._chunks
            if _matches_scope(
                chunk.metadata,
                organization_id=organization_id,
                metadata_filter=metadata_filter,
                score=chunk.similarity_score,
                score_threshold=score_threshold,
            )
        ][:max_docs]
        return KnowledgebaseResult(
            query=query,
            context="\n\n".join(chunk.text for chunk in results),
            sources=results,
            confidence=results[0].similarity_score if results else None,
            zero_hit=not results,
            latency_ms=0,
        )


def sign_kb_webhook_payload(
    payload: dict[str, Any],
    secret: str,
) -> tuple[bytes, str]:
    """Return a signed webhook body after removing sensitive file metadata."""

    safe_payload = _sanitize_payload(payload)
    body = json.dumps(safe_payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, f"sha256={signature}"


def _matches_scope(
    metadata: dict[str, Any],
    *,
    organization_id: UUID | str,
    metadata_filter: dict[str, Any],
    score: float | None,
    score_threshold: float,
) -> bool:
    if metadata.get("organization_id") != str(organization_id):
        return False
    if (score or 0.0) < score_threshold:
        return False

    source_type = metadata_filter.get("source_type")
    if source_type is not None and metadata.get("source_type") != source_type:
        return False

    if metadata.get("source_type") == "conversation_file":
        requested_conversation_id = metadata_filter.get("conversation_id")
        return (
            requested_conversation_id is not None
            and metadata.get("conversation_id") == str(requested_conversation_id)
        )

    if metadata.get("source_type") == "admin_upload":
        visibility_filter = metadata_filter.get("visibility_policy")
        if visibility_filter is not None:
            return metadata.get("visibility_policy") == visibility_filter
        return True

    return False


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "metadata" and isinstance(value, dict):
            sanitized[key] = _sanitize_metadata(value)
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_payload(value)
        else:
            sanitized[key] = value
    return sanitized


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in _SENSITIVE_WEBHOOK_METADATA:
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_metadata(value)
        else:
            sanitized[key] = value
    return sanitized
