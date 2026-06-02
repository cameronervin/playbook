"""SQLAlchemy model for kb.langchain_pg_embedding.

LangChain-pgvector compatible embedding table. The ``embedding`` column is a
pgvector VECTOR whose dimension matches ``settings.KB_EMBED_DIMENSIONS`` (1536).
"""
from __future__ import annotations

import uuid

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VectorEmbedding(Base):
    __tablename__ = "langchain_pg_embedding"
    __table_args__ = {"schema": "kb"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb.langchain_pg_collection.uuid", ondelete="CASCADE"),
        nullable=True,
    )
    # Dimension fixed at 1536 to match settings.KB_EMBED_DIMENSIONS.
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(1536), nullable=True)
    document: Mapped[str | None] = mapped_column(Text, nullable=True)
    cmetadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
