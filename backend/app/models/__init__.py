"""ORM models. Import every model here for Alembic autodiscovery."""

from app.models.base import Base
from app.models.example import Example

__all__ = ["Base", "Example"]
