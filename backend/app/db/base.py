"""Aggregates model imports so Alembic and SQLAlchemy see every table.

Importing this module guarantees that all ORM models are registered on
``Base.metadata`` before ``create_all`` / autogenerate runs. Add new model
imports here as the data layer grows.
"""

from app.models.base import Base  # noqa: F401
from app.models.example import Example  # noqa: F401

__all__ = ["Base", "Example"]
