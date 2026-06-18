"""Package export checks for KB document service modules."""

from __future__ import annotations


def test_kb_document_package_exports_match_focused_modules() -> None:
    from app.services import kb_documents
    from app.services.kb_documents.admin_document_service import KBDocumentService
    from app.services.kb_documents.mappers import (
        kb_document_to_response,
        kb_event_to_response,
    )
    from app.services.kb_documents.upload_service import KBDocumentUpload
    from app.services.kb_documents.webhook_service import KBDocumentWebhookService

    assert kb_documents.KBDocumentService is KBDocumentService
    assert kb_documents.KBDocumentUpload is KBDocumentUpload
    assert kb_documents.KBDocumentWebhookService is KBDocumentWebhookService
    assert kb_documents.kb_document_to_response is kb_document_to_response
    assert kb_documents.kb_event_to_response is kb_event_to_response
