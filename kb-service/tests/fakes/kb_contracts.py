from __future__ import annotations

from typing import Any
from uuid import UUID

from app.schemas.ingest import IngestConversationFileRequest, IngestDocumentRequest


def build_ingest_metadata(
    request: IngestDocumentRequest | IngestConversationFileRequest,
) -> dict[str, Any]:
    """Build safe, trusted source metadata for contract tests."""

    metadata = {
        **request.metadata_tags,
        "source_type": request.source_type,
        "organization_id": str(request.organization_id),
        "source_title": request.source_title,
        "visibility_policy": request.visibility_policy,
        "metadata_tags": request.metadata_tags,
        "content_type": request.content_type,
        "size_bytes": request.size_bytes,
        "status_webhook_url": request.status_webhook_url,
        "webhook_enabled": bool(request.status_webhook_url),
    }
    if isinstance(request, IngestDocumentRequest):
        metadata.update(
            {
                "playbook_document_id": str(request.playbook_document_id),
                "source_date": request.source_date.isoformat()
                if request.source_date
                else None,
            }
        )
    else:
        metadata.update(
            {
                "conversation_id": str(request.conversation_id),
                "conversation_file_id": str(request.conversation_file_id),
            }
        )
    return metadata


class FakePrivateRetrieval:
    """In-memory retrieval fake that enforces current source-type filters."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def search(
        self,
        *,
        organization_id: UUID,
        source_type: str,
        conversation_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in self._rows:
            metadata = row.get("metadata", {})
            if metadata.get("organization_id") != str(organization_id):
                continue
            if metadata.get("source_type") != source_type:
                continue
            if source_type == "conversation_file":
                if conversation_id is None:
                    continue
                if metadata.get("conversation_id") != str(conversation_id):
                    continue
            results.append(row)
        return results


class FakeSummaryProvider:
    """Deterministic summary fake with extractive fallback behavior."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def summarize(self, *, filename: str, text: str) -> str:
        first_passage = text.strip().splitlines()[0].strip()
        if self.should_fail:
            return f"{filename}: {first_passage}"
        return f"Summary for {filename}: {first_passage}"
