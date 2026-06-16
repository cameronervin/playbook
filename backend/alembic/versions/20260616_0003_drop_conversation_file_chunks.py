"""drop backend-local conversation file chunks

Revision ID: 20260616_0003
Revises: 20260605_0002
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260616_0003"
down_revision: str | None = "20260605_0002"
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


def _jsonb_object_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.drop_index(
        "ix_conversation_file_chunks_file_id",
        table_name="conversation_file_chunks",
        if_exists=True,
    )
    op.drop_table("conversation_file_chunks", if_exists=True)


def downgrade() -> None:
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
        "ix_conversation_file_chunks_file_id",
        "conversation_file_chunks",
        ["file_id"],
    )
