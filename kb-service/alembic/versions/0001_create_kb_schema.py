"""Create kb schema, all KB tables, pgvector column + HNSW index.

Revision ID: 0001
Revises: —
Create Date: 2026-06-02

This single migration is the consolidated head for the scaffold. It folds what
were five incremental migrations in the source service into one clean baseline:
  * 0001 — schema + base tables + initial vector cast + HNSW index
  * 0002 — hardened DB-side defaults, status CHECK constraints, supporting
           indexes (collection_id, cmetadata GIN), pgcrypto extension
  * 0003 — ingestion_logs.parse_result (parser route telemetry)
  * 0004 — ingestion_logs.pipeline_task_id (Celery chain root tracking) + index
  * 0005 — functional index on cmetadata->>'document_id' (fast re-ingest DELETE)

Tables created (all in schema ``kb``):
  kb.configurations
  kb.documents
  kb.ingestion_logs
  kb.langchain_pg_collection
  kb.langchain_pg_embedding  +  pgvector(1536) column + HNSW index

No ``public.*`` tables are touched — the host application owns those.

pgvector graceful degradation: the ``vector`` extension, the vector(1536) column
cast, and the HNSW index are only applied when pgvector is available in the
target Postgres. On a plain Postgres (e.g. local dev without pgvector) the
``embedding`` column stays TEXT and the migration still succeeds. DevOps MUST
install pgvector before running this in staging/prod for similarity search to work.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pgvector_available() -> bool:
    """Return True if the pgvector extension is installable in this Postgres."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. Extensions + schema
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid()
    if _pgvector_available():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS kb")

    # ------------------------------------------------------------------
    # 1. kb.configurations
    # ------------------------------------------------------------------
    op.create_table(
        "configurations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("collection_name", sa.String(255), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parse_config", JSONB(), nullable=False),
        sa.Column("chunk_config", JSONB(), nullable=False),
        sa.Column("embed_config", JSONB(), nullable=False),
        sa.Column("vectorstore_config", JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema="kb",
    )

    # ------------------------------------------------------------------
    # 2. kb.documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "configuration_id",
            UUID(as_uuid=True),
            sa.ForeignKey("kb.configurations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("md5", sa.String(32), nullable=False),
        sa.Column("s3_key", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("configuration_id", "md5", name="uq_kb_documents_config_md5"),
        sa.CheckConstraint(
            "status IN ('pending', 'parsing', 'chunking', 'embedding', 'loading', 'success', 'failed')",
            name="ck_kb_documents_status_valid",
        ),
        schema="kb",
    )
    op.create_index("ix_kb_documents_configuration_id", "documents", ["configuration_id"], schema="kb")
    op.create_index("ix_kb_documents_status", "documents", ["status"], schema="kb")

    # ------------------------------------------------------------------
    # 3. kb.ingestion_logs  (includes parse_result + pipeline_task_id folded in)
    # ------------------------------------------------------------------
    op.create_table(
        "ingestion_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("kb.documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pipeline_task_id", sa.String(255), nullable=True),
        sa.Column("parse_task_id", sa.String(255), nullable=True),
        sa.Column("chunk_task_id", sa.String(255), nullable=True),
        sa.Column("embed_task_id", sa.String(255), nullable=True),
        sa.Column("load_vector_task_id", sa.String(255), nullable=True),
        sa.Column("parse_status", sa.String(50), nullable=True),
        sa.Column("chunk_status", sa.String(50), nullable=True),
        sa.Column("embed_status", sa.String(50), nullable=True),
        sa.Column("load_vector_status", sa.String(50), nullable=True),
        sa.Column("parse_result", JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "parse_status IS NULL OR parse_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_parse_status_valid",
        ),
        sa.CheckConstraint(
            "chunk_status IS NULL OR chunk_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_chunk_status_valid",
        ),
        sa.CheckConstraint(
            "embed_status IS NULL OR embed_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_embed_status_valid",
        ),
        sa.CheckConstraint(
            "load_vector_status IS NULL OR load_vector_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
            name="ck_kb_ingestion_logs_load_vector_status_valid",
        ),
        schema="kb",
    )
    op.create_index("ix_kb_ingestion_logs_document_id", "ingestion_logs", ["document_id"], schema="kb")
    op.create_index(
        "ix_kb_ingestion_logs_pipeline_task_id", "ingestion_logs", ["pipeline_task_id"], schema="kb"
    )

    # ------------------------------------------------------------------
    # 4. kb.langchain_pg_collection
    # ------------------------------------------------------------------
    op.create_table(
        "langchain_pg_collection",
        sa.Column("uuid", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("cmetadata", JSONB(), nullable=True),
        schema="kb",
    )

    # ------------------------------------------------------------------
    # 5. kb.langchain_pg_embedding
    # ------------------------------------------------------------------
    op.create_table(
        "langchain_pg_embedding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "collection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("kb.langchain_pg_collection.uuid", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("embedding", sa.Text(), nullable=True),  # cast to vector(1536) below
        sa.Column("document", sa.Text(), nullable=True),
        sa.Column("cmetadata", JSONB(), nullable=True),
        schema="kb",
    )

    # Cast embedding column to vector(1536), build the HNSW + supporting indexes.
    # All require pgvector — skipped gracefully if the extension is unavailable.
    if _pgvector_available():
        op.execute(
            "ALTER TABLE kb.langchain_pg_embedding "
            "ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector(1536)"
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_kb_embedding_hnsw
                ON kb.langchain_pg_embedding
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
        )

    # These indexes do not require pgvector.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_embedding_collection_id "
        "ON kb.langchain_pg_embedding (collection_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_embedding_cmetadata_gin "
        "ON kb.langchain_pg_embedding USING gin (cmetadata)"
    )
    # Functional index on cmetadata->>'document_id' — turns the per-re-ingest
    # DELETE WHERE cmetadata->>'document_id' = X from a full scan into an index seek.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kb_embedding_document_id
        ON kb.langchain_pg_embedding ((cmetadata->>'document_id'))
        """
    )


def downgrade() -> None:
    if _pgvector_available():
        op.execute("DROP INDEX IF EXISTS kb.ix_kb_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS kb.ix_kb_embedding_document_id")
    op.execute("DROP INDEX IF EXISTS kb.ix_kb_embedding_cmetadata_gin")
    op.execute("DROP INDEX IF EXISTS kb.ix_kb_embedding_collection_id")
    op.drop_table("langchain_pg_embedding", schema="kb")
    op.drop_table("langchain_pg_collection", schema="kb")
    op.drop_index("ix_kb_ingestion_logs_pipeline_task_id", table_name="ingestion_logs", schema="kb")
    op.drop_index("ix_kb_ingestion_logs_document_id", table_name="ingestion_logs", schema="kb")
    op.drop_table("ingestion_logs", schema="kb")
    op.drop_index("ix_kb_documents_status", table_name="documents", schema="kb")
    op.drop_index("ix_kb_documents_configuration_id", table_name="documents", schema="kb")
    op.drop_table("documents", schema="kb")
    op.drop_table("configurations", schema="kb")
    op.execute("DROP SCHEMA IF EXISTS kb CASCADE")
