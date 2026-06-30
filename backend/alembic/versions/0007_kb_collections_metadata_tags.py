"""add KB collections and managed metadata tags

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
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


def upgrade() -> None:
    op.create_table(
        "kb_collections",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_kb_collections_org_slug"),
    )
    op.create_index("ix_kb_collections_organization_id", "kb_collections", ["organization_id"])
    op.create_index("ix_kb_collections_is_active", "kb_collections", ["is_active"])

    op.create_table(
        "kb_metadata_tags",
        _uuid_pk_column(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_kb_metadata_tags_org_slug"),
    )
    op.create_index("ix_kb_metadata_tags_organization_id", "kb_metadata_tags", ["organization_id"])
    op.create_index("ix_kb_metadata_tags_is_active", "kb_metadata_tags", ["is_active"])

    op.add_column(
        "kb_documents",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_kb_documents_collection_id_kb_collections",
        "kb_documents",
        "kb_collections",
        ["collection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_kb_documents_collection_id", "kb_documents", ["collection_id"])

    op.create_table(
        "kb_document_tags",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        _created_at_column(),
        sa.ForeignKeyConstraint(["document_id"], ["kb_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["kb_metadata_tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "tag_id"),
    )
    op.create_index("ix_kb_document_tags_tag_id", "kb_document_tags", ["tag_id"])

    _seed_defaults()
    _backfill_documents()


def downgrade() -> None:
    op.drop_index("ix_kb_document_tags_tag_id", table_name="kb_document_tags")
    op.drop_table("kb_document_tags")
    op.drop_index("ix_kb_documents_collection_id", table_name="kb_documents")
    op.drop_constraint(
        "fk_kb_documents_collection_id_kb_collections",
        "kb_documents",
        type_="foreignkey",
    )
    op.drop_column("kb_documents", "collection_id")
    op.drop_index("ix_kb_metadata_tags_is_active", table_name="kb_metadata_tags")
    op.drop_index("ix_kb_metadata_tags_organization_id", table_name="kb_metadata_tags")
    op.drop_table("kb_metadata_tags")
    op.drop_index("ix_kb_collections_is_active", table_name="kb_collections")
    op.drop_index("ix_kb_collections_organization_id", table_name="kb_collections")
    op.drop_table("kb_collections")


def _seed_defaults() -> None:
    op.execute(
        """
        INSERT INTO kb_collections (
            organization_id, slug, title, description, icon, sort_order
        )
        SELECT organizations.id, defaults.slug, defaults.title, defaults.description,
               defaults.icon, defaults.sort_order
        FROM organizations
        CROSS JOIN (
            VALUES
                ('compliance', 'Compliance & NIL',
                 'NIL, eligibility, and recruiting rules - kept current with department and NCAA policy.',
                 'shield', 10),
                ('travel', 'Team Travel',
                 'Per-diem rates, charter logistics, and team hotel policy for every sport.',
                 'plane', 20),
                ('academics', 'Academic Services',
                 'Study-hall rules, tutoring, and academic eligibility support.',
                 'book-open', 30),
                ('donor', 'Donor Relations',
                 'Giving levels, suite benefits, and booster club answers for boosters.',
                 'users', 40)
        ) AS defaults(slug, title, description, icon, sort_order)
        ON CONFLICT (organization_id, slug) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO kb_metadata_tags (organization_id, slug, label, sort_order)
        SELECT organizations.id, defaults.slug, defaults.label, defaults.sort_order
        FROM organizations
        CROSS JOIN (
            VALUES
                ('nil', 'NIL', 10),
                ('compliance', 'Compliance', 20),
                ('eligibility', 'Eligibility', 30),
                ('recruiting', 'Recruiting', 40),
                ('transfer', 'Transfer', 50),
                ('travel', 'Travel', 60),
                ('per-diem', 'Per diem', 70),
                ('academics', 'Academics', 80),
                ('tutoring', 'Tutoring', 90),
                ('donor-relations', 'Donor relations', 100),
                ('boosters', 'Boosters', 110),
                ('policy', 'Policy', 120),
                ('operations', 'Operations', 130)
        ) AS defaults(slug, label, sort_order)
        ON CONFLICT (organization_id, slug) DO NOTHING
        """
    )


def _backfill_documents() -> None:
    op.execute(
        """
        UPDATE kb_documents AS doc
        SET collection_id = collection.id
        FROM kb_collections AS collection
        WHERE collection.organization_id = doc.organization_id
          AND collection.slug = NULLIF(doc.metadata_tags ->> 'collection', '')
        """
    )
    op.execute(
        """
        UPDATE kb_documents AS doc
        SET collection_id = collection.id
        FROM kb_collections AS collection
        WHERE doc.collection_id IS NULL
          AND collection.organization_id = doc.organization_id
          AND collection.slug = 'compliance'
        """
    )
    op.execute(
        """
        WITH raw_values AS (
            SELECT doc.id AS document_id, doc.organization_id, doc.metadata_tags ->> 'collection' AS value
            FROM kb_documents AS doc
            WHERE doc.metadata_tags ? 'collection'
            UNION ALL
            SELECT doc.id, doc.organization_id, doc.metadata_tags ->> 'topic'
            FROM kb_documents AS doc
            WHERE doc.metadata_tags ? 'topic'
            UNION ALL
            SELECT doc.id, doc.organization_id, doc.metadata_tags ->> 'category'
            FROM kb_documents AS doc
            WHERE doc.metadata_tags ? 'category'
            UNION ALL
            SELECT doc.id, doc.organization_id, jsonb_array_elements_text(doc.metadata_tags -> 'topics')
            FROM kb_documents AS doc
            WHERE jsonb_typeof(doc.metadata_tags -> 'topics') = 'array'
            UNION ALL
            SELECT doc.id, doc.organization_id, jsonb_array_elements_text(doc.metadata_tags -> 'tags')
            FROM kb_documents AS doc
            WHERE jsonb_typeof(doc.metadata_tags -> 'tags') = 'array'
        ),
        normalized_values AS (
            SELECT
                document_id,
                organization_id,
                trim(both '-' from regexp_replace(lower(value), '[^a-z0-9]+', '-', 'g')) AS slug
            FROM raw_values
            WHERE value IS NOT NULL AND btrim(value) <> ''
        )
        INSERT INTO kb_document_tags (document_id, tag_id)
        SELECT DISTINCT normalized_values.document_id, tag.id
        FROM normalized_values
        JOIN kb_metadata_tags AS tag
          ON tag.organization_id = normalized_values.organization_id
         AND tag.slug = normalized_values.slug
        ON CONFLICT DO NOTHING
        """
    )
