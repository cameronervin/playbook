"""add direct upload requests and kb ingest outbox

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upload_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("kb_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "conversation_file_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'pending'::text"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "request_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            """
            (
                source_type = 'admin_upload'
                AND kb_document_id IS NOT NULL
                AND conversation_file_id IS NULL
            )
            OR
            (
                source_type = 'conversation_file'
                AND conversation_file_id IS NOT NULL
                AND kb_document_id IS NULL
            )
            """,
            name="ck_upload_requests_exact_resource",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_file_id"],
            ["conversation_files.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["kb_document_id"],
            ["kb_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_upload_requests_conversation_file_id",
        "upload_requests",
        ["conversation_file_id"],
    )
    op.create_index(
        "ix_upload_requests_kb_document_id",
        "upload_requests",
        ["kb_document_id"],
    )
    op.create_index(
        "ix_upload_requests_organization_id",
        "upload_requests",
        ["organization_id"],
    )
    op.create_index(
        "ix_upload_requests_requested_by",
        "upload_requests",
        ["requested_by"],
    )
    op.create_index(
        "ix_upload_requests_source_type",
        "upload_requests",
        ["source_type"],
    )
    op.create_index(
        "ix_upload_requests_status_expires_at",
        "upload_requests",
        ["status", "expires_at"],
    )

    op.create_table(
        "kb_ingest_outbox",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("kb_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "conversation_file_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'pending'::text"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "kb_service_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("kb_task_id", sa.String(length=255), nullable=True),
        sa.Column(
            "failure_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            """
            (
                source_type = 'admin_upload'
                AND kb_document_id IS NOT NULL
                AND conversation_file_id IS NULL
            )
            OR
            (
                source_type = 'conversation_file'
                AND conversation_file_id IS NOT NULL
                AND kb_document_id IS NULL
            )
            """,
            name="ck_kb_ingest_outbox_exact_resource",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_file_id"],
            ["conversation_files.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["kb_document_id"],
            ["kb_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "conversation_file_id",
            name="uq_kb_ingest_outbox_conversation_file",
        ),
        sa.UniqueConstraint(
            "source_type",
            "kb_document_id",
            name="uq_kb_ingest_outbox_admin_document",
        ),
    )
    op.create_index(
        "ix_kb_ingest_outbox_conversation_file_id",
        "kb_ingest_outbox",
        ["conversation_file_id"],
    )
    op.create_index(
        "ix_kb_ingest_outbox_kb_document_id",
        "kb_ingest_outbox",
        ["kb_document_id"],
    )
    op.create_index(
        "ix_kb_ingest_outbox_kb_service_document_id",
        "kb_ingest_outbox",
        ["kb_service_document_id"],
    )
    op.create_index(
        "ix_kb_ingest_outbox_organization_id",
        "kb_ingest_outbox",
        ["organization_id"],
    )
    op.create_index(
        "ix_kb_ingest_outbox_source_type",
        "kb_ingest_outbox",
        ["source_type"],
    )
    op.create_index(
        "ix_kb_ingest_outbox_status_next_attempt_at",
        "kb_ingest_outbox",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kb_ingest_outbox_status_next_attempt_at",
        table_name="kb_ingest_outbox",
    )
    op.drop_index("ix_kb_ingest_outbox_source_type", table_name="kb_ingest_outbox")
    op.drop_index(
        "ix_kb_ingest_outbox_organization_id",
        table_name="kb_ingest_outbox",
    )
    op.drop_index(
        "ix_kb_ingest_outbox_kb_service_document_id",
        table_name="kb_ingest_outbox",
    )
    op.drop_index(
        "ix_kb_ingest_outbox_kb_document_id",
        table_name="kb_ingest_outbox",
    )
    op.drop_index(
        "ix_kb_ingest_outbox_conversation_file_id",
        table_name="kb_ingest_outbox",
    )
    op.drop_table("kb_ingest_outbox")

    op.drop_index("ix_upload_requests_status_expires_at", table_name="upload_requests")
    op.drop_index("ix_upload_requests_source_type", table_name="upload_requests")
    op.drop_index("ix_upload_requests_requested_by", table_name="upload_requests")
    op.drop_index("ix_upload_requests_organization_id", table_name="upload_requests")
    op.drop_index("ix_upload_requests_kb_document_id", table_name="upload_requests")
    op.drop_index(
        "ix_upload_requests_conversation_file_id",
        table_name="upload_requests",
    )
    op.drop_table("upload_requests")
