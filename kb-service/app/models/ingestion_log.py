"""SQLAlchemy model for kb.ingestion_logs.

One row per document ingest attempt — tracks per-stage task IDs and statuses.
This is KB's internal source of truth for pipeline progress; the calling app
learns about progress via the outbound status webhook, not this table.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"
    __table_args__ = (
        CheckConstraint(
            "parse_status IS NULL OR parse_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_parse_status_valid",
        ),
        CheckConstraint(
            "chunk_status IS NULL OR chunk_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_chunk_status_valid",
        ),
        CheckConstraint(
            "embed_status IS NULL OR embed_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_embed_status_valid",
        ),
        CheckConstraint(
            "load_vector_status IS NULL OR load_vector_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_load_vector_status_valid",
        ),
        {"schema": "kb"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb.documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pipeline_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    parse_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embed_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    load_vector_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parse_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    chunk_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embed_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    load_vector_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parse_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
