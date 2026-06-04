"""Metadata tests for the Playbook product schema."""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models import Base

EXPECTED_PLAYBOOK_TABLES = {
    "organizations",
    "users",
    "conversations",
    "conversation_messages",
    "message_citations",
    "conversation_files",
    "conversation_file_chunks",
    "kb_documents",
    "kb_document_events",
    "dashboard_insight_runs",
    "dashboard_insights",
    "admin_chat_sessions",
    "admin_chat_messages",
    "audit_logs",
}


def test_playbook_tables_are_registered_without_scaffold_examples() -> None:
    table_names = set(Base.metadata.tables)

    assert EXPECTED_PLAYBOOK_TABLES.issubset(table_names)
    assert "examples" not in table_names


def test_domain_model_modules_export_registered_models() -> None:
    from app.models import (
        AdminChatMessage,
        AdminChatSession,
        AuditLog,
        Conversation,
        ConversationFile,
        ConversationFileChunk,
        ConversationMessage,
        DashboardInsight,
        DashboardInsightRun,
        KBDocument,
        KBDocumentEvent,
        MessageCitation,
        Organization,
        User,
    )
    from app.models.analytics import (
        AdminChatMessage as AnalyticsAdminChatMessage,
        AdminChatSession as AnalyticsAdminChatSession,
        DashboardInsight as AnalyticsDashboardInsight,
        DashboardInsightRun as AnalyticsDashboardInsightRun,
    )
    from app.models.audit import AuditLog as AuditAuditLog
    from app.models.conversations import (
        Conversation as ConversationsConversation,
        ConversationFile as ConversationsConversationFile,
        ConversationFileChunk as ConversationsConversationFileChunk,
        ConversationMessage as ConversationsConversationMessage,
        MessageCitation as ConversationsMessageCitation,
    )
    from app.models.identity import Organization as IdentityOrganization
    from app.models.identity import User as IdentityUser
    from app.models.knowledge_base import KBDocument as KnowledgeBaseKBDocument
    from app.models.knowledge_base import KBDocumentEvent as KnowledgeBaseKBDocumentEvent

    assert IdentityOrganization is Organization
    assert IdentityUser is User
    assert ConversationsConversation is Conversation
    assert ConversationsConversationMessage is ConversationMessage
    assert ConversationsMessageCitation is MessageCitation
    assert ConversationsConversationFile is ConversationFile
    assert ConversationsConversationFileChunk is ConversationFileChunk
    assert KnowledgeBaseKBDocument is KBDocument
    assert KnowledgeBaseKBDocumentEvent is KBDocumentEvent
    assert AnalyticsDashboardInsightRun is DashboardInsightRun
    assert AnalyticsDashboardInsight is DashboardInsight
    assert AnalyticsAdminChatSession is AdminChatSession
    assert AnalyticsAdminChatMessage is AdminChatMessage
    assert AuditAuditLog is AuditLog


def test_users_constraints_match_playbook_identity_model() -> None:
    users = Base.metadata.tables["users"]
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in users.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert isinstance(users.c.id.type, PG_UUID)
    assert users.c.organization_id.foreign_keys
    assert users.c.role.server_default.arg.text == "'athlete'::text"
    assert ("organization_id", "email") in unique_columns
    assert ("auth_provider", "provider_subject") in unique_columns
    assert "hashed_password" not in users.c
    assert "is_superuser" not in users.c
    assert "is_verified" not in users.c


def test_jsonb_columns_have_server_defaults() -> None:
    expected_jsonb_defaults = {
        "organizations": {"theme_config": "'{}'::jsonb"},
        "conversation_messages": {
            "topic_labels": "'[]'::jsonb",
            "risk_labels": "'[]'::jsonb",
            "metadata": "'{}'::jsonb",
        },
        "message_citations": {"source_metadata": "'{}'::jsonb"},
        "conversation_files": {"extraction_metadata": "'{}'::jsonb"},
        "conversation_file_chunks": {
            "source_locator": "'{}'::jsonb",
            "metadata": "'{}'::jsonb",
        },
        "kb_documents": {
            "visibility_policy": """'{"scope":"all_athletes"}'::jsonb""",
            "metadata_tags": "'{}'::jsonb",
        },
        "kb_document_events": {"metadata": "'{}'::jsonb"},
        "dashboard_insight_runs": {"source_filters": "'{}'::jsonb"},
        "dashboard_insights": {
            "headline_cards": "'[]'::jsonb",
            "topic_breakdown": "'[]'::jsonb",
            "unanswered_questions": "'[]'::jsonb",
            "risk_breakdown": "'[]'::jsonb",
            "recommended_attention_areas": "'[]'::jsonb",
            "source_message_ids": "'[]'::jsonb",
        },
        "admin_chat_messages": {
            "references": "'[]'::jsonb",
            "metadata": "'{}'::jsonb",
        },
        "audit_logs": {"metadata": "'{}'::jsonb"},
    }

    for table_name, columns in expected_jsonb_defaults.items():
        table = Base.metadata.tables[table_name]
        for column_name, server_default in columns.items():
            assert isinstance(table.c[column_name].type, JSONB)
            assert table.c[column_name].server_default.arg.text == server_default


def test_key_foreign_key_delete_behaviors_are_explicit() -> None:
    expected_ondelete = {
        ("users", ("organization_id",)): "CASCADE",
        ("conversations", ("organization_id",)): "CASCADE",
        ("conversations", ("athlete_id",)): "CASCADE",
        ("conversation_messages", ("conversation_id",)): "CASCADE",
        ("message_citations", ("message_id",)): "CASCADE",
        ("conversation_files", ("conversation_id",)): "CASCADE",
        ("conversation_files", ("message_id",)): "SET NULL",
        ("conversation_file_chunks", ("file_id",)): "CASCADE",
        ("kb_documents", ("organization_id",)): "CASCADE",
        ("kb_document_events", ("document_id",)): "CASCADE",
        ("dashboard_insight_runs", ("requested_by",)): "SET NULL",
        ("dashboard_insights", ("run_id",)): "CASCADE",
        ("admin_chat_sessions", ("created_by",)): "CASCADE",
        ("admin_chat_messages", ("session_id",)): "CASCADE",
        ("audit_logs", ("actor_user_id",)): "SET NULL",
    }

    for (table_name, constrained_columns), ondelete in expected_ondelete.items():
        table = Base.metadata.tables[table_name]
        matching_constraints = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
            and tuple(constraint.column_keys) == constrained_columns
        ]

        assert matching_constraints
        assert matching_constraints[0].ondelete == ondelete


def test_operational_indexes_are_registered() -> None:
    expected_indexes = {
        "ix_users_organization_id",
        "ix_users_role",
        "ix_conversations_athlete_id",
        "ix_conversation_messages_conversation_id",
        "ix_conversation_files_conversation_id",
        "ix_conversation_file_chunks_file_id",
        "ix_kb_documents_organization_id",
        "ix_kb_documents_processing_status",
        "ix_dashboard_insight_runs_organization_id",
        "ix_dashboard_insights_run_id",
        "ix_admin_chat_sessions_organization_id",
        "ix_admin_chat_messages_session_id",
        "ix_audit_logs_organization_id",
    }
    registered_indexes = {
        index.name for table in Base.metadata.tables.values() for index in table.indexes
    }

    assert expected_indexes.issubset(registered_indexes)
