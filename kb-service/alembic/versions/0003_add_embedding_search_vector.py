"""Add full-text search vector to KB embeddings.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE kb.langchain_pg_embedding
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english'::regconfig, coalesce(document, ''))
        ) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kb_embedding_search_vector_gin
        ON kb.langchain_pg_embedding
        USING gin (search_vector)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS kb.ix_kb_embedding_search_vector_gin")
    op.execute(
        """
        ALTER TABLE kb.langchain_pg_embedding
        DROP COLUMN IF EXISTS search_vector
        """
    )
