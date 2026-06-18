"""Package export checks for KB ingest outbox service modules."""

from __future__ import annotations

from pathlib import Path


def test_kb_ingest_outbox_package_exports_match_focused_modules() -> None:
    from app.services import kb_ingest_outbox
    from app.services.kb_ingest_outbox.admin_upload_handler import AdminUploadHandler
    from app.services.kb_ingest_outbox.conversation_file_handler import (
        ConversationFileHandler,
    )
    from app.services.kb_ingest_outbox.failure_policy import (
        OutboxFailurePolicy,
        OutboxResourceMismatchError,
        OutboxResourceMissingError,
    )
    from app.services.kb_ingest_outbox.service import (
        KbIngestOutboxDrainResult,
        KbIngestOutboxService,
    )

    assert kb_ingest_outbox.AdminUploadHandler is AdminUploadHandler
    assert kb_ingest_outbox.ConversationFileHandler is ConversationFileHandler
    assert kb_ingest_outbox.KbIngestOutboxDrainResult is KbIngestOutboxDrainResult
    assert kb_ingest_outbox.KbIngestOutboxService is KbIngestOutboxService
    assert kb_ingest_outbox.OutboxFailurePolicy is OutboxFailurePolicy
    assert kb_ingest_outbox.OutboxResourceMismatchError is OutboxResourceMismatchError
    assert kb_ingest_outbox.OutboxResourceMissingError is OutboxResourceMissingError


def test_backend_code_uses_kb_ingest_outbox_package_imports() -> None:
    legacy_import = "app.services.kb_ingest_outbox_service"
    backend_root = Path(__file__).resolve().parents[2]

    offenders = [
        path
        for path in backend_root.rglob("*.py")
        if "__pycache__" not in path.parts
        and path != Path(__file__)
        and legacy_import in path.read_text()
    ]

    assert offenders == []
