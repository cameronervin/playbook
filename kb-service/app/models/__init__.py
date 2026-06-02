"""KB service ORM models — import all so Alembic autodiscovery works.

Importing every model here ensures they all register on ``Base.metadata``
before Alembic introspects it for migration autogeneration.
"""
from __future__ import annotations

from app.models.base import Base
from app.models.configuration import Configuration
from app.models.document import Document
from app.models.ingestion_log import IngestionLog
from app.models.vector_collection import VectorCollection
from app.models.vector_embedding import VectorEmbedding

__all__ = [
    "Base",
    "Configuration",
    "Document",
    "IngestionLog",
    "VectorCollection",
    "VectorEmbedding",
]
