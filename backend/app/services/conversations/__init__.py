"""Focused athlete conversation service modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.conversations.file_service import (
        ConversationFileService,
        ConversationFileUpload,
    )
    from app.services.conversations.history_service import ConversationHistoryService
    from app.services.conversations.message_service import ConversationMessageService
    from app.services.conversations.service import ConversationService

__all__ = [
    "ConversationFileService",
    "ConversationFileUpload",
    "ConversationHistoryService",
    "ConversationMessageService",
    "ConversationService",
]


def __getattr__(name: str) -> Any:
    """Lazily expose conversation service classes without import-time side effects."""
    if name in {"ConversationFileService", "ConversationFileUpload"}:
        from app.services.conversations import file_service

        return getattr(file_service, name)
    if name == "ConversationHistoryService":
        from app.services.conversations.history_service import (
            ConversationHistoryService,
        )

        return ConversationHistoryService
    if name == "ConversationMessageService":
        from app.services.conversations.message_service import (
            ConversationMessageService,
        )

        return ConversationMessageService
    if name == "ConversationService":
        from app.services.conversations.service import ConversationService

        return ConversationService
    raise AttributeError(name)
