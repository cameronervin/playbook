"""Declarative base for KB service SQLAlchemy models.

All KB models live in the dedicated ``kb`` Postgres schema (set per-model via
``__table_args__``) so this service can share a Postgres instance with the
calling app while staying isolated.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
