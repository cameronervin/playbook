"""add kb ingestion mirror fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kb_documents", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "kb_documents",
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "conversation_files",
        sa.Column(
            "kb_service_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "conversation_files",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "conversation_files",
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversation_files_kb_service_document_id",
        "conversation_files",
        ["kb_service_document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_files_kb_service_document_id",
        table_name="conversation_files",
    )
    op.drop_column("conversation_files", "chunk_count")
    op.drop_column("conversation_files", "summary")
    op.drop_column("conversation_files", "kb_service_document_id")
    op.drop_column("kb_documents", "chunk_count")
    op.drop_column("kb_documents", "summary")
