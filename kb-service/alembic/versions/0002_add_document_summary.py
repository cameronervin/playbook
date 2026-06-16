"""Add canonical source summary to KB documents.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-16
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True), schema="kb")
    op.add_column(
        "ingestion_logs",
        sa.Column("summarize_task_id", sa.String(255), nullable=True),
        schema="kb",
    )
    op.add_column(
        "ingestion_logs",
        sa.Column("summarize_status", sa.String(50), nullable=True),
        schema="kb",
    )
    op.create_check_constraint(
        "ck_kb_ingestion_logs_summarize_status_valid",
        "ingestion_logs",
        "summarize_status IS NULL OR summarize_status IN ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'REVOKED')",
        schema="kb",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_kb_ingestion_logs_summarize_status_valid",
        "ingestion_logs",
        schema="kb",
    )
    op.drop_column("ingestion_logs", "summarize_status", schema="kb")
    op.drop_column("ingestion_logs", "summarize_task_id", schema="kb")
    op.drop_column("documents", "summary", schema="kb")
