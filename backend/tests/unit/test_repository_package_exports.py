"""Repository package export compatibility tests."""

from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.repositories.conversations.citation_repo import (
    MessageCitationRepository as FocusedMessageCitationRepository,
)
from app.repositories.conversations.conversation_repo import (
    ConversationRepository as FocusedConversationRepository,
)
from app.repositories.conversations.file_repo import (
    ConversationFileRepository as FocusedConversationFileRepository,
)
from app.repositories.conversations.message_repo import (
    ConversationMessageRepository as FocusedConversationMessageRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository
from app.repositories.uploads.kb_ingest_outbox_repo import (
    KBIngestOutboxRepository as FocusedKBIngestOutboxRepository,
)
from app.repositories.uploads.upload_request_repo import (
    UploadRequestRepository as FocusedUploadRequestRepository,
)


def test_conversation_repository_facade_exports_focused_classes() -> None:
    assert ConversationRepository is FocusedConversationRepository
    assert ConversationMessageRepository is FocusedConversationMessageRepository
    assert MessageCitationRepository is FocusedMessageCitationRepository
    assert ConversationFileRepository is FocusedConversationFileRepository


def test_upload_repository_facade_exports_focused_classes() -> None:
    assert UploadRequestRepository is FocusedUploadRequestRepository
    assert KBIngestOutboxRepository is FocusedKBIngestOutboxRepository
