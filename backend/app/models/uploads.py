"""Direct-upload request and KB ingest outbox models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._columns import (
    created_at_column,
    jsonb_object_column,
    updated_at_column,
    uuid_primary_key,
)
from app.models.base import Base


class UploadRequest(Base):
    """Backend-owned direct-upload lifecycle request."""

    __tablename__ = "upload_requests"
    __table_args__ = (
        CheckConstraint(
            """
            (
                source_type = 'admin_upload'
                AND kb_document_id IS NOT NULL
                AND conversation_file_id IS NULL
            )
            OR
            (
                source_type = 'conversation_file'
                AND conversation_file_id IS NOT NULL
                AND kb_document_id IS NULL
            )
            """,
            name="ck_upload_requests_exact_resource",
        ),
        Index("ix_upload_requests_organization_id", "organization_id"),
        Index("ix_upload_requests_requested_by", "requested_by"),
        Index("ix_upload_requests_source_type", "source_type"),
        Index("ix_upload_requests_status_expires_at", "status", "expires_at"),
        Index("ix_upload_requests_kb_document_id", "kb_document_id"),
        Index("ix_upload_requests_conversation_file_id", "conversation_file_id"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    kb_document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    conversation_file_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversation_files.id", ondelete="CASCADE"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'pending'::text"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    request_metadata: Mapped[dict[str, Any]] = jsonb_object_column()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class KBIngestOutbox(Base):
    """Durable backend-to-KB-service ingest dispatch row."""

    __tablename__ = "kb_ingest_outbox"
    __table_args__ = (
        CheckConstraint(
            """
            (
                source_type = 'admin_upload'
                AND kb_document_id IS NOT NULL
                AND conversation_file_id IS NULL
            )
            OR
            (
                source_type = 'conversation_file'
                AND conversation_file_id IS NOT NULL
                AND kb_document_id IS NULL
            )
            """,
            name="ck_kb_ingest_outbox_exact_resource",
        ),
        UniqueConstraint(
            "source_type",
            "kb_document_id",
            name="uq_kb_ingest_outbox_admin_document",
        ),
        UniqueConstraint(
            "source_type",
            "conversation_file_id",
            name="uq_kb_ingest_outbox_conversation_file",
        ),
        Index("ix_kb_ingest_outbox_organization_id", "organization_id"),
        Index("ix_kb_ingest_outbox_source_type", "source_type"),
        Index(
            "ix_kb_ingest_outbox_status_next_attempt_at",
            "status",
            "next_attempt_at",
        ),
        Index("ix_kb_ingest_outbox_kb_document_id", "kb_document_id"),
        Index("ix_kb_ingest_outbox_conversation_file_id", "conversation_file_id"),
        Index("ix_kb_ingest_outbox_kb_service_document_id", "kb_service_document_id"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    kb_document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    conversation_file_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversation_files.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'pending'::text"),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    kb_service_document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    kb_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_metadata: Mapped[dict[str, Any]] = jsonb_object_column()
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
