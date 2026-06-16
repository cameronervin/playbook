"""SQLAlchemy model for kb.documents.

Each row represents a file the calling app submitted for ingestion.
The ``id`` is the KB-service document identifier returned from
POST /api/kb/ingest/document. The caller's Playbook document id is preserved in
``metadata.playbook_document_id``.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("configuration_id", "md5", name="uq_kb_documents_config_md5"),
        CheckConstraint(
            "status IN ('pending', 'parsing', 'chunking', 'embedding', 'loading', 'success', 'failed')",
            name="ck_kb_documents_status_valid",
        ),
        {"schema": "kb"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb.configurations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    md5: Mapped[str] = mapped_column(String(32), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", server_default=text("'pending'")
    )
    # Mapped to the SQL column "metadata"; the Python attribute is "metadata_"
    # because "metadata" is reserved on the SQLAlchemy declarative base.
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
