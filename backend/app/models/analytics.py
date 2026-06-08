"""Admin analytics, insight, and chat models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._columns import (
    created_at_column,
    jsonb_array_column,
    jsonb_object_column,
    updated_at_column,
    uuid_primary_key,
)
from app.models.base import Base


class DashboardInsightRun(Base):
    """Lifecycle record for dashboard insight generation."""

    __tablename__ = "dashboard_insight_runs"
    __table_args__ = (
        Index("ix_dashboard_insight_runs_organization_id", "organization_id"),
        Index("ix_dashboard_insight_runs_requested_by", "requested_by"),
        Index("ix_dashboard_insight_runs_status", "status"),
        Index("ix_dashboard_insight_runs_window", "window_start", "window_end"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'pending'::text"),
        nullable=False,
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_filters: Mapped[dict[str, Any]] = jsonb_object_column()
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class DashboardInsight(Base):
    """Generated dashboard insight output."""

    __tablename__ = "dashboard_insights"
    __table_args__ = (
        Index("ix_dashboard_insights_run_id", "run_id"),
        Index("ix_dashboard_insights_generated_at", "generated_at"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dashboard_insight_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    headline_cards: Mapped[list[Any]] = jsonb_array_column()
    topic_breakdown: Mapped[list[Any]] = jsonb_array_column()
    unanswered_questions: Mapped[list[Any]] = jsonb_array_column()
    risk_breakdown: Mapped[list[Any]] = jsonb_array_column()
    recommended_attention_areas: Mapped[list[Any]] = jsonb_array_column()
    source_message_ids: Mapped[list[Any]] = jsonb_array_column()
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


class AdminChatSession(Base):
    """Admin-only chat session over analytics and insight data."""

    __tablename__ = "admin_chat_sessions"
    __table_args__ = (
        Index("ix_admin_chat_sessions_organization_id", "organization_id"),
        Index("ix_admin_chat_sessions_created_by", "created_by"),
        Index("ix_admin_chat_sessions_status", "status"),
        Index("ix_admin_chat_sessions_last_message_at", "last_message_at"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'active'::text"),
        nullable=False,
    )
    context_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    context_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class AdminChatMessage(Base):
    """Message in an admin analytics chat session."""

    __tablename__ = "admin_chat_messages"
    __table_args__ = (
        Index("ix_admin_chat_messages_session_id", "session_id"),
        Index("ix_admin_chat_messages_role", "role"),
        Index("ix_admin_chat_messages_status", "status"),
        Index("ix_admin_chat_messages_created_at", "created_at"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'complete'::text"),
        nullable=False,
    )
    references: Mapped[list[Any]] = jsonb_array_column()
    message_metadata: Mapped[dict[str, Any]] = jsonb_object_column("metadata")
    created_at: Mapped[datetime] = created_at_column()
