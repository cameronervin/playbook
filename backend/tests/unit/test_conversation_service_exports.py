"""Package export checks for conversation service modules."""

from __future__ import annotations

from pathlib import Path


def test_conversation_package_exports_match_focused_modules() -> None:
    from app.services import conversations
    from app.services.conversations.file_service import ConversationFileUpload
    from app.services.conversations.history_service import ConversationHistoryService
    from app.services.conversations.message_service import ConversationMessageService
    from app.services.conversations.service import ConversationService

    assert conversations.ConversationService is ConversationService
    assert conversations.ConversationFileUpload is ConversationFileUpload
    assert conversations.ConversationHistoryService is ConversationHistoryService
    assert conversations.ConversationMessageService is ConversationMessageService


def test_backend_code_uses_conversation_service_package_imports() -> None:
    legacy_import = "app.services.conversation_service"
    backend_root = Path(__file__).resolve().parents[2]

    offenders = [
        path
        for path in backend_root.rglob("*.py")
        if "__pycache__" not in path.parts
        and path != Path(__file__)
        and legacy_import in path.read_text()
    ]

    assert offenders == []
