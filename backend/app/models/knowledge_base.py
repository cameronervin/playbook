"""Knowledge base document tracking models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._columns import (
    created_at_column,
    jsonb_object_column,
    updated_at_column,
    uuid_primary_key,
)
from app.models.base import Base


class KBDocument(Base):
    """Backend-side record for an admin-uploaded KB document."""

    __tablename__ = "kb_documents"
    __table_args__ = (
        Index("ix_kb_documents_organization_id", "organization_id"),
        Index("ix_kb_documents_uploaded_by", "uploaded_by"),
        Index("ix_kb_documents_processing_status", "processing_status"),
        Index("ix_kb_documents_kb_service_document_id", "kb_service_document_id"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'uploaded'::text"),
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("""'{"scope":"all_athletes"}'::jsonb"""),
        nullable=False,
    )
    metadata_tags: Mapped[dict[str, Any]] = jsonb_object_column()
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_official: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    kb_service_document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class KBDocumentEvent(Base):
    """Lifecycle event for a KB document."""

    __tablename__ = "kb_document_events"
    __table_args__ = (
        Index("ix_kb_document_events_document_id", "document_id"),
        Index("ix_kb_document_events_event_type", "event_type"),
        Index("ix_kb_document_events_created_at", "created_at"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = jsonb_object_column("metadata")
    created_at: Mapped[datetime] = created_at_column()
