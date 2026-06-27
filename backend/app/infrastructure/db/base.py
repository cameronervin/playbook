"""Aggregates model imports so Alembic and SQLAlchemy see every table.

Importing this module guarantees that all ORM models are registered on
``Base.metadata`` before ``create_all`` / autogenerate runs. Add new model
imports here as the data layer grows.
"""

from app.models import (  # noqa: F401
    AdminChatMessage,
    AdminChatSession,
    AuditLog,
    Base,
    Conversation,
    ConversationFile,
    ConversationMessage,
    DashboardInsight,
    DashboardInsightRun,
    KBDocument,
    KBDocumentEvent,
    MessageCitation,
    Organization,
    User,
)

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
    "KBDocument",
    "KBDocumentEvent",
    "MessageCitation",
    "Organization",
    "User",
]
