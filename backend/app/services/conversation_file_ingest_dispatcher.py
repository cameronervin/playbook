"""Conversation-file KB ingest dispatch seam for the phase 1 upload slice."""

from __future__ import annotations

import structlog

from app.schemas.knowledgebase import KBConversationFileIngestRequest

logger = structlog.get_logger(__name__)


class ConversationFileIngestDispatcher:
    """No-op dispatcher that records intent through structured logs.

    Phase 1 builds and validates the trusted backend-derived request, but does
    not call KB-service until the private ingest contract is implemented.
    """

    async def dispatch(self, request: KBConversationFileIngestRequest) -> None:
        logger.info(
            "conversation_file_ingest_dispatch_noop",
            organization_id=str(request.organization_id),
            conversation_id=str(request.conversation_id),
            conversation_file_id=str(request.conversation_file_id),
            content_type=request.content_type,
            size_bytes=request.size_bytes,
        )
