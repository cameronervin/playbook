"""SQLAlchemy model for kb.langchain_pg_collection.

LangChain-pgvector compatible collection table. Each configuration maps to one
collection row (looked up / created by ``collection_name``).
"""
from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VectorCollection(Base):
    __tablename__ = "langchain_pg_collection"
    __table_args__ = {"schema": "kb"}

    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    cmetadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
