"""create playbook product schema

Revision ID: 20260604_0001
Revises: None
Create Date: 2026-06-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260604_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _jsonb_object_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def _jsonb_array_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(),
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.drop_table("examples", if_exists=True)

    op.create_table(
        "organizations",
        _uuid_pk_column(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        _jsonb_object_column("theme_config"),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        _created_at_column(),
        _updated_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_is_active", "organizations", ["is_active"])

    op.create_table(
        "users",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.String(length=40),
            server_default=sa.text("'athlete'::text"),
            nullable=False,
        ),
        sa.Column("auth_provider", sa.String(length=40), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("sport_team", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "email", name="uq_users_organization_email"
        ),
        sa.UniqueConstraint(
            "auth_provider", "provider_subject", name="uq_users_provider_subject"
        ),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "conversations",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'active'::text"),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(["athlete_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_organization_id", "conversations", ["organization_id"]
    )
    op.create_index("ix_conversations_athlete_id", "conversations", ["athlete_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index(
        "ix_conversations_last_message_at", "conversations", ["last_message_at"]
    )

    op.create_table(
        "conversation_messages",
        _uuid_pk_column(),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'complete'::text"),
            nullable=False,
        ),
        sa.Column("safety_outcome", sa.String(length=80), nullable=True),
        _jsonb_array_column("topic_labels"),
        _jsonb_array_column("risk_labels"),
        _jsonb_object_column("metadata"),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_conversation_id",
        "conversation_messages",
        ["conversation_id"],
    )
    op.create_index("ix_conversation_messages_role", "conversation_messages", ["role"])
    op.create_index(
        "ix_conversation_messages_status", "conversation_messages", ["status"]
    )
    op.create_index(
        "ix_conversation_messages_created_at", "conversation_messages", ["created_at"]
    )

    op.create_table(
        "message_citations",
        _uuid_pk_column(),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_title", sa.String(length=500), nullable=False),
        _jsonb_object_column("source_metadata"),
        sa.Column("rank", sa.Integer(), nullable=False),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["message_id"], ["conversation_messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_citations_message_id", "message_citations", ["message_id"]
    )
    op.create_index(
        "ix_message_citations_document_id", "message_citations", ["document_id"]
    )
    op.create_index("ix_message_citations_chunk_id", "message_citations", ["chunk_id"])

    op.create_table(
        "conversation_files",
        _uuid_pk_column(),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column(
            "extraction_status",
            sa.String(length=40),
            server_default=sa.text("'uploaded'::text"),
            nullable=False,
        ),
        sa.Column("extracted_text_ref", sa.String(length=1000), nullable=True),
        sa.Column("extracted_text_sha256", sa.String(length=64), nullable=True),
        sa.Column("extracted_char_count", sa.Integer(), nullable=True),
        _jsonb_object_column("extraction_metadata"),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["conversation_messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_files_conversation_id",
        "conversation_files",
        ["conversation_id"],
    )
    op.create_index(
        "ix_conversation_files_message_id", "conversation_files", ["message_id"]
    )
    op.create_index(
        "ix_conversation_files_uploaded_by", "conversation_files", ["uploaded_by"]
    )
    op.create_index(
        "ix_conversation_files_extraction_status",
        "conversation_files",
        ["extraction_status"],
    )

    op.create_table(
        "conversation_file_chunks",
        _uuid_pk_column(),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        _jsonb_object_column("source_locator"),
        _jsonb_object_column("metadata"),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["file_id"], ["conversation_files.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "file_id", "chunk_index", name="uq_conversation_file_chunks_file_index"
        ),
    )
    op.create_index(
        "ix_conversation_file_chunks_file_id", "conversation_file_chunks", ["file_id"]
    )

    op.create_table(
        "kb_documents",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column(
            "processing_status",
            sa.String(length=40),
            server_default=sa.text("'uploaded'::text"),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "visibility_policy",
            postgresql.JSONB(),
            server_default=sa.text("""'{"scope":"all_athletes"}'::jsonb"""),
            nullable=False,
        ),
        _jsonb_object_column("metadata_tags"),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column(
            "is_official", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "priority", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "kb_service_document_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kb_documents_organization_id", "kb_documents", ["organization_id"]
    )
    op.create_index("ix_kb_documents_uploaded_by", "kb_documents", ["uploaded_by"])
    op.create_index(
        "ix_kb_documents_processing_status", "kb_documents", ["processing_status"]
    )
    op.create_index(
        "ix_kb_documents_kb_service_document_id",
        "kb_documents",
        ["kb_service_document_id"],
    )

    op.create_table(
        "kb_document_events",
        _uuid_pk_column(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        _jsonb_object_column("metadata"),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["document_id"], ["kb_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kb_document_events_document_id", "kb_document_events", ["document_id"]
    )
    op.create_index(
        "ix_kb_document_events_event_type", "kb_document_events", ["event_type"]
    )
    op.create_index(
        "ix_kb_document_events_created_at", "kb_document_events", ["created_at"]
    )

    op.create_table(
        "dashboard_insight_runs",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'pending'::text"),
            nullable=False,
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        _jsonb_object_column("source_filters"),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dashboard_insight_runs_organization_id",
        "dashboard_insight_runs",
        ["organization_id"],
    )
    op.create_index(
        "ix_dashboard_insight_runs_requested_by",
        "dashboard_insight_runs",
        ["requested_by"],
    )
    op.create_index(
        "ix_dashboard_insight_runs_status", "dashboard_insight_runs", ["status"]
    )
    op.create_index(
        "ix_dashboard_insight_runs_window",
        "dashboard_insight_runs",
        ["window_start", "window_end"],
    )

    op.create_table(
        "dashboard_insights",
        _uuid_pk_column(),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        _jsonb_array_column("headline_cards"),
        _jsonb_array_column("topic_breakdown"),
        _jsonb_array_column("unanswered_questions"),
        _jsonb_array_column("risk_breakdown"),
        _jsonb_array_column("recommended_attention_areas"),
        _jsonb_array_column("source_message_ids"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["dashboard_insight_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dashboard_insights_run_id", "dashboard_insights", ["run_id"])
    op.create_index(
        "ix_dashboard_insights_generated_at", "dashboard_insights", ["generated_at"]
    )

    op.create_table(
        "admin_chat_sessions",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'active'::text"),
            nullable=False,
        ),
        sa.Column("context_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_chat_sessions_organization_id",
        "admin_chat_sessions",
        ["organization_id"],
    )
    op.create_index(
        "ix_admin_chat_sessions_created_by", "admin_chat_sessions", ["created_by"]
    )
    op.create_index("ix_admin_chat_sessions_status", "admin_chat_sessions", ["status"])
    op.create_index(
        "ix_admin_chat_sessions_last_message_at",
        "admin_chat_sessions",
        ["last_message_at"],
    )

    op.create_table(
        "admin_chat_messages",
        _uuid_pk_column(),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'complete'::text"),
            nullable=False,
        ),
        _jsonb_array_column("references"),
        _jsonb_object_column("metadata"),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["session_id"], ["admin_chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_chat_messages_session_id", "admin_chat_messages", ["session_id"]
    )
    op.create_index("ix_admin_chat_messages_role", "admin_chat_messages", ["role"])
    op.create_index("ix_admin_chat_messages_status", "admin_chat_messages", ["status"])
    op.create_index(
        "ix_admin_chat_messages_created_at", "admin_chat_messages", ["created_at"]
    )

    op.create_table(
        "audit_logs",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        _jsonb_object_column("metadata"),
        _created_at_column(),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs", if_exists=True)
    op.drop_table("admin_chat_messages", if_exists=True)
    op.drop_table("admin_chat_sessions", if_exists=True)
    op.drop_table("dashboard_insights", if_exists=True)
    op.drop_table("dashboard_insight_runs", if_exists=True)
    op.drop_table("kb_document_events", if_exists=True)
    op.drop_table("kb_documents", if_exists=True)
    op.drop_table("conversation_file_chunks", if_exists=True)
    op.drop_table("conversation_files", if_exists=True)
    op.drop_table("message_citations", if_exists=True)
    op.drop_table("conversation_messages", if_exists=True)
    op.drop_table("conversations", if_exists=True)
    op.drop_table("users", if_exists=True)
    op.drop_table("organizations", if_exists=True)

    op.create_table(
        "examples",
        _uuid_pk_column(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'active'::text"),
            nullable=False,
        ),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_examples_status", "examples", ["status"])
