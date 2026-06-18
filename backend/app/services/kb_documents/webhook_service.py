"""Signed KB-service webhook processing."""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.knowledge_base import KBDocument
from app.repositories.conversations import ConversationFileRepository
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from app.schemas.kb_documents import KBWebhookPayload, KBWebhookResponse
from app.services.kb_documents.status_mapping import (
    admin_kb_service_document_id,
    chunk_count_from_metadata,
    document_kb_service_document_id,
    map_kb_webhook_status,
    sanitize_failure_reason,
)

logger = structlog.get_logger(__name__)


class KBDocumentWebhookService:
    """Processes signed status callbacks from the KB service."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        document_repo: KBDocumentRepository | None = None,
        event_repo: KBDocumentEventRepository | None = None,
        file_repo: ConversationFileRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.event_repo = event_repo or KBDocumentEventRepository(session)
        self.file_repo = file_repo or ConversationFileRepository(session)

    async def process(
        self,
        *,
        payload: KBWebhookPayload,
        raw_body: bytes,
        signature: str | None,
    ) -> KBWebhookResponse:
        """Verify signature, route status by source type, and mirror safe metadata."""
        self._verify_signature(raw_body=raw_body, signature=signature)
        self._verify_timestamp(payload.timestamp)

        if payload.source_type == "conversation_file":
            return await self._process_conversation_file(payload)
        return await self._process_admin_upload(payload)

    async def _process_admin_upload(
        self,
        payload: KBWebhookPayload,
    ) -> KBWebhookResponse:
        """Mirror a KB-service webhook into an admin KB document row."""
        document = await self._resolve_admin_document(payload)
        status = map_kb_webhook_status(payload.status, payload.stage)
        failure_reason = (
            sanitize_failure_reason(payload.error_message)
            if status == "failed"
            else None
        )
        await self.document_repo.update_status(
            document,
            processing_status=status,
            failure_reason=failure_reason,
        )
        mirror_update: dict[str, Any] = {}
        kb_service_document_id = admin_kb_service_document_id(payload)
        if kb_service_document_id is not None:
            mirror_update["kb_service_document_id"] = kb_service_document_id
        if payload.summary is not None:
            mirror_update["summary"] = payload.summary
        chunk_count = chunk_count_from_metadata(payload.metadata)
        if chunk_count is not None:
            mirror_update["chunk_count"] = chunk_count
        if mirror_update:
            await self.document_repo.update_ingestion_mirror(
                document,
                **mirror_update,
            )
        await self.event_repo.create(
            document_id=document.id,
            event_type=f"kb.{payload.stage or 'pipeline'}.{payload.status.lower()}",
            status=status,
            message=failure_reason,
            metadata={
                **payload.metadata,
                "raw_status": payload.status,
                "stage": payload.stage,
                "source_type": payload.source_type or "admin_upload",
                "kb_service_document_id": document_kb_service_document_id(document),
            },
            created_at=datetime.now(UTC),
        )
        await self.session.commit()
        logger.info(
            "kb_webhook_processed",
            source_type=payload.source_type or "admin_upload",
            document_id=str(document.id),
            status=status,
            stage=payload.stage,
        )
        return KBWebhookResponse(document_status=status)  # type: ignore[arg-type]

    async def _process_conversation_file(
        self,
        payload: KBWebhookPayload,
    ) -> KBWebhookResponse:
        """Mirror a KB-service webhook into a conversation file row."""
        if payload.conversation_id is None or payload.conversation_file_id is None:
            raise NotFoundError("Conversation file", str(payload.document_id))

        file = await self.file_repo.get_for_conversation(
            conversation_id=payload.conversation_id,
            file_id=payload.conversation_file_id,
        )
        if file is None:
            kb_service_document_id = payload.kb_service_document_id or payload.document_id
            file = await self.file_repo.get_by_kb_service_document_id(
                kb_service_document_id
            )
            if file is None or file.conversation_id != payload.conversation_id:
                raise NotFoundError(
                    "Conversation file",
                    str(payload.conversation_file_id),
                )

        status = map_kb_webhook_status(payload.status, payload.stage)
        file_status = "extracting" if status == "processing" else status
        failure_reason = (
            sanitize_failure_reason(payload.error_message)
            if status == "failed"
            else None
        )
        await self.file_repo.update_extraction_status(
            file,
            extraction_status=file_status,
            error_message=failure_reason,
        )
        mirror_update: dict[str, Any] = {
            "kb_service_document_id": payload.kb_service_document_id
            or payload.document_id
        }
        if payload.summary is not None:
            mirror_update["summary"] = payload.summary
        chunk_count = chunk_count_from_metadata(payload.metadata)
        if chunk_count is not None:
            mirror_update["chunk_count"] = chunk_count
        await self.file_repo.update_ingestion_mirror(file, **mirror_update)
        await self.session.commit()
        logger.info(
            "kb_webhook_processed",
            source_type="conversation_file",
            conversation_id=str(file.conversation_id),
            conversation_file_id=str(file.id),
            status=file_status,
            stage=payload.stage,
        )
        return KBWebhookResponse(document_status=status)  # type: ignore[arg-type]

    async def _resolve_admin_document(self, payload: KBWebhookPayload) -> KBDocument:
        if payload.playbook_document_id is not None:
            document = await self.document_repo.get(payload.playbook_document_id)
            if document is not None:
                return document

        document = await self.document_repo.get(payload.document_id)
        if document is None:
            document = await self.document_repo.get_by_kb_service_document_id(
                payload.document_id
            )
        if document is None:
            raise NotFoundError("KB document", str(payload.document_id))
        return document

    def _verify_signature(self, *, raw_body: bytes, signature: str | None) -> None:
        if not self.settings.KB_WEBHOOK_SECRET:
            raise ForbiddenError("KB webhook secret is not configured")
        if not signature:
            raise ForbiddenError("Missing KB webhook signature")
        expected = hmac.new(
            self.settings.KB_WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        supplied = signature.removeprefix("sha256=")
        if not hmac.compare_digest(expected, supplied):
            raise ForbiddenError("Invalid KB webhook signature")

    @staticmethod
    def _verify_timestamp(timestamp: int | None) -> None:
        if timestamp is None:
            return
        if abs(int(time.time()) - timestamp) > 600:
            raise ForbiddenError("Stale KB webhook timestamp")
