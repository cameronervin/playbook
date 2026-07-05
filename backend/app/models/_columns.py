"""Shared column factories for Playbook ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


def uuid_primary_key() -> Mapped[UUID]:
    """Return the standard Playbook UUID primary key column."""
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def created_at_column() -> Mapped[datetime]:
    """Return the standard creation timestamp column."""
    return mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


def updated_at_column() -> Mapped[datetime]:
    """Return the standard update timestamp column."""
    return mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


def jsonb_object_column(column_name: str | None = None) -> Mapped[dict[str, Any]]:
    """Return a JSONB object column with a server-side empty-object default."""
    return mapped_column(
        column_name,
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )


def jsonb_array_column(column_name: str | None = None) -> Mapped[list[Any]]:
    """Return a JSONB array column with a server-side empty-array default."""
    return mapped_column(
        column_name,
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
