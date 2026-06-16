"""Athlete conversation, message, citation, and file models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._columns import (
    created_at_column,
    jsonb_array_column,
    jsonb_object_column,
    updated_at_column,
    uuid_primary_key,
)
from app.models.base import Base


class Conversation(Base):
    """Athlete support conversation."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_organization_id", "organization_id"),
        Index("ix_conversations_athlete_id", "athlete_id"),
        Index("ix_conversations_status", "status"),
        Index("ix_conversations_last_message_at", "last_message_at"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'active'::text"),
        nullable=False,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class ConversationMessage(Base):
    """Single message within an athlete conversation."""

    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ix_conversation_messages_conversation_id", "conversation_id"),
        Index("ix_conversation_messages_role", "role"),
        Index("ix_conversation_messages_status", "status"),
        Index("ix_conversation_messages_created_at", "created_at"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'complete'::text"),
        nullable=False,
    )
    safety_outcome: Mapped[str | None] = mapped_column(String(80), nullable=True)
    topic_labels: Mapped[list[Any]] = jsonb_array_column()
    risk_labels: Mapped[list[Any]] = jsonb_array_column()
    message_metadata: Mapped[dict[str, Any]] = jsonb_object_column("metadata")
    created_at: Mapped[datetime] = created_at_column()


class MessageCitation(Base):
    """Source citation attached to an assistant message."""

    __tablename__ = "message_citations"
    __table_args__ = (
        Index("ix_message_citations_message_id", "message_id"),
        Index("ix_message_citations_document_id", "document_id"),
        Index("ix_message_citations_chunk_id", "chunk_id"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    message_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    chunk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_metadata: Mapped[dict[str, Any]] = jsonb_object_column()
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class ConversationFile(Base):
    """Athlete-uploaded file scoped to a conversation."""

    __tablename__ = "conversation_files"
    __table_args__ = (
        Index("ix_conversation_files_conversation_id", "conversation_id"),
        Index("ix_conversation_files_message_id", "message_id"),
        Index("ix_conversation_files_uploaded_by", "uploaded_by"),
        Index("ix_conversation_files_extraction_status", "extraction_status"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    extraction_status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'uploaded'::text"),
        nullable=False,
    )
    extracted_text_ref: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    extracted_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_metadata: Mapped[dict[str, Any]] = jsonb_object_column()
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

