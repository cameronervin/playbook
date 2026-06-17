"""ORM models. Import every model here for Alembic autodiscovery."""

from app.models.analytics import (
    AdminChatMessage,
    AdminChatSession,
    DashboardInsight,
    DashboardInsightRun,
)
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.conversations import (
    Conversation,
    ConversationFile,
    ConversationMessage,
    MessageCitation,
)
from app.models.identity import OAuthAccount, Organization, User
from app.models.knowledge_base import KBDocument, KBDocumentEvent
from app.models.uploads import KBIngestOutbox, UploadRequest

__all__ = [
    "AdminChatMessage",
    "AdminChatSession",
    "AuditLog",
    "Base",
    "Conversation",
    "ConversationFile",
    "ConversationMessage",
    "DashboardInsight",
    "DashboardInsightRun",
    "KBIngestOutbox",
    "KBDocument",
    "KBDocumentEvent",
    "MessageCitation",
    "OAuthAccount",
    "Organization",
    "UploadRequest",
    "User",
]
