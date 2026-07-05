"""SQLAlchemy model for kb.configurations.

Each row represents a named pipeline configuration (parse/chunk/embed/vectorstore
settings). The calling app creates one configuration per scope it wants to keep
isolated (e.g. per tenant or per knowledge area).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Configuration(Base):
    __tablename__ = "configurations"
    __table_args__ = {"schema": "kb", "extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    collection_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    parse_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    chunk_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embed_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    vectorstore_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
