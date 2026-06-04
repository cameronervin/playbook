"""Organization and user identity models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._columns import (
    created_at_column,
    jsonb_object_column,
    updated_at_column,
    uuid_primary_key,
)
from app.models.base import Base


class Organization(Base):
    """Tenant organization for a college athletic department."""

    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organizations_is_active", "is_active"),)

    id: Mapped[UUID] = uuid_primary_key()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    theme_config: Mapped[dict[str, Any]] = jsonb_object_column()
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class User(Base):
    """Playbook user profile and role record."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "email", name="uq_users_organization_email"
        ),
        UniqueConstraint(
            "auth_provider", "provider_subject", name="uq_users_provider_subject"
        ),
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'athlete'::text"),
        nullable=False,
    )
    auth_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    sport_team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
