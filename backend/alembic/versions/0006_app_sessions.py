"""add app sessions

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamp_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.text("now()"),
        nullable=nullable,
    )


def upgrade() -> None:
    op.create_table(
        "app_sessions",
        _uuid_pk_column(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        _timestamp_column("last_seen_at"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _timestamp_column("revoked_at", nullable=True),
        sa.Column("revoked_reason", sa.String(length=80), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_sessions_user_id", "app_sessions", ["user_id"])
    op.create_index("ix_app_sessions_expires_at", "app_sessions", ["expires_at"])
    op.create_index("ix_app_sessions_revoked_at", "app_sessions", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_app_sessions_revoked_at", table_name="app_sessions")
    op.drop_index("ix_app_sessions_expires_at", table_name="app_sessions")
    op.drop_index("ix_app_sessions_user_id", table_name="app_sessions")
    op.drop_table("app_sessions")
