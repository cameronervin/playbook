"""Organization and user identity models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
        Index("ix_users_is_superuser", "is_superuser"),
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
    hashed_password: Mapped[str] = mapped_column(
        String(1024),
        server_default=text("''::text"),
        nullable=False,
    )
    sport_team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    app_sessions: Mapped[list["AppSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AppSession(Base):
    """Server-side Playbook application session for sliding JWT renewal."""

    __tablename__ = "app_sessions"
    __table_args__ = (
        Index("ix_app_sessions_user_id", "user_id"),
        Index("ix_app_sessions_expires_at", "expires_at"),
        Index("ix_app_sessions_revoked_at", "revoked_at"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    user: Mapped[User] = relationship(back_populates="app_sessions")


class OAuthAccount(Base):
    """OAuth account record compatible with FastAPI Users' OAuth adapter shape."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint(
            "oauth_name",
            "account_id",
            name="uq_oauth_accounts_provider_account",
        ),
        Index("ix_oauth_accounts_user_id", "user_id"),
        Index("ix_oauth_accounts_provider", "oauth_name"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    oauth_name: Mapped[str] = mapped_column(String(100), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    user: Mapped[User] = relationship(back_populates="oauth_accounts")
