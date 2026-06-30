"""Knowledge-base collection and metadata-tag catalog services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.identity import User
from app.models.knowledge_base import KBCollection, KBDocument, KBMetadataTag
from app.repositories.knowledge_base import (
    KBCollectionRepository,
    KBDocumentTagRepository,
    KBMetadataTagRepository,
)
from app.schemas.kb_documents import (
    KBCollectionCreateRequest,
    KBCollectionResponse,
    KBMetadataTagCreateRequest,
    KBMetadataTagResponse,
    KBMetadataTagUpdateRequest,
)
from app.services.audit_service import AuditLogService

SUPPORTED_KB_COLLECTION_ICONS = {"shield", "plane", "book-open", "users", "database"}

DEFAULT_KB_COLLECTIONS = [
    {
        "slug": "compliance",
        "title": "Compliance & NIL",
        "description": "NIL, eligibility, and recruiting rules - kept current with department and NCAA policy.",
        "icon": "shield",
        "sort_order": 10,
    },
    {
        "slug": "travel",
        "title": "Team Travel",
        "description": "Per-diem rates, charter logistics, and team hotel policy for every sport.",
        "icon": "plane",
        "sort_order": 20,
    },
    {
        "slug": "academics",
        "title": "Academic Services",
        "description": "Study-hall rules, tutoring, and academic eligibility support.",
        "icon": "book-open",
        "sort_order": 30,
    },
    {
        "slug": "donor",
        "title": "Donor Relations",
        "description": "Giving levels, suite benefits, and booster club answers for boosters.",
        "icon": "users",
        "sort_order": 40,
    },
]

DEFAULT_KB_METADATA_TAGS = [
    ("nil", "NIL"),
    ("compliance", "Compliance"),
    ("eligibility", "Eligibility"),
    ("recruiting", "Recruiting"),
    ("transfer", "Transfer"),
    ("travel", "Travel"),
    ("per-diem", "Per diem"),
    ("academics", "Academics"),
    ("tutoring", "Tutoring"),
    ("donor-relations", "Donor relations"),
    ("boosters", "Boosters"),
    ("policy", "Policy"),
    ("operations", "Operations"),
]

MANAGED_METADATA_KEYS = {
    "collection",
    "collection_title",
    "tag_slugs",
    "tags",
    "topics",
}


@dataclass(frozen=True)
class ResolvedDocumentMetadata:
    """Validated collection, tags, and composed KB-service metadata."""

    collection: KBCollection
    tags: list[KBMetadataTag]
    metadata_tags: dict[str, Any]


class KBCatalogService:
    """Service for KB collections and global metadata tag presets."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        collection_repo: KBCollectionRepository | None = None,
        tag_repo: KBMetadataTagRepository | None = None,
        document_tag_repo: KBDocumentTagRepository | None = None,
        audit_service: AuditLogService | None = None,
    ) -> None:
        self.session = session
        self.collection_repo = collection_repo or KBCollectionRepository(session)
        self.tag_repo = tag_repo or KBMetadataTagRepository(session)
        self.document_tag_repo = document_tag_repo or KBDocumentTagRepository(session)
        self.audit_service = audit_service or AuditLogService(session)

    async def ensure_defaults(self, organization_id: UUID) -> bool:
        """Create default catalog rows for organizations that do not have them."""
        created_defaults = False
        existing_collections = await self.collection_repo.list_by_organization(
            organization_id,
            active_only=False,
        )
        if not existing_collections:
            created_defaults = True
            for item in DEFAULT_KB_COLLECTIONS:
                await self.collection_repo.create(organization_id=organization_id, **item)

        existing_tags = await self.tag_repo.list_by_organization(
            organization_id,
            active_only=False,
        )
        if not existing_tags:
            created_defaults = True
            for index, (slug, label) in enumerate(DEFAULT_KB_METADATA_TAGS, start=1):
                await self.tag_repo.create(
                    organization_id=organization_id,
                    slug=slug,
                    label=label,
                    sort_order=index * 10,
                )
        return created_defaults

    async def list_collections(self, *, actor: User) -> list[KBCollectionResponse]:
        """Return active KB collections for the actor's organization."""
        if await self.ensure_defaults(actor.organization_id):
            await self.session.commit()
        rows = await self.collection_repo.list_by_organization(actor.organization_id)
        return [kb_collection_to_response(row) for row in rows]

    async def create_collection(
        self,
        *,
        actor: User,
        request: KBCollectionCreateRequest,
    ) -> KBCollectionResponse:
        """Create a super-admin managed KB collection."""
        if request.icon not in SUPPORTED_KB_COLLECTION_ICONS:
            raise ValidationError("Unsupported KB collection icon")
        await self.ensure_defaults(actor.organization_id)
        slug = await self._unique_collection_slug(actor.organization_id, request.title)
        collection = await self.collection_repo.create(
            organization_id=actor.organization_id,
            slug=slug,
            title=request.title.strip(),
            description=request.description.strip(),
            icon=request.icon,
            sort_order=await self._next_collection_sort_order(actor.organization_id),
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.collection_created",
            target_type="kb_collection",
            target_id=collection.id,
            metadata={"slug": collection.slug, "title": collection.title},
        )
        await self.session.commit()
        return kb_collection_to_response(collection)

    async def list_tags(
        self,
        *,
        actor: User,
        include_archived: bool = False,
    ) -> list[KBMetadataTagResponse]:
        """Return global metadata tag presets for the actor's organization."""
        if await self.ensure_defaults(actor.organization_id):
            await self.session.commit()
        rows = await self.tag_repo.list_by_organization(
            actor.organization_id,
            active_only=not include_archived,
        )
        return [kb_metadata_tag_to_response(row) for row in rows]

    async def create_tag(
        self,
        *,
        actor: User,
        request: KBMetadataTagCreateRequest,
    ) -> KBMetadataTagResponse:
        """Create a super-admin managed global metadata tag."""
        await self.ensure_defaults(actor.organization_id)
        slug = slugify(request.label)
        if not slug:
            raise ValidationError("Metadata tag label must contain letters or numbers")
        existing = await self.tag_repo.get_by_slug(
            organization_id=actor.organization_id,
            slug=slug,
        )
        if existing is not None:
            raise ValidationError("Metadata tag already exists")
        tag = await self.tag_repo.create(
            organization_id=actor.organization_id,
            slug=slug,
            label=request.label.strip(),
            sort_order=await self._next_tag_sort_order(actor.organization_id),
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.metadata_tag_created",
            target_type="kb_metadata_tag",
            target_id=tag.id,
            metadata={"slug": tag.slug, "label": tag.label},
        )
        await self.session.commit()
        return kb_metadata_tag_to_response(tag)

    async def update_tag(
        self,
        *,
        actor: User,
        tag_id: UUID,
        request: KBMetadataTagUpdateRequest,
    ) -> KBMetadataTagResponse:
        """Update editable metadata tag fields."""
        tag = await self._get_tag_or_404(actor, tag_id)
        updated = await self.tag_repo.update(tag, label=request.label.strip())
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.metadata_tag_updated",
            target_type="kb_metadata_tag",
            target_id=tag.id,
            metadata={"slug": tag.slug, "label": updated.label},
        )
        await self.session.commit()
        return kb_metadata_tag_to_response(updated)

    async def archive_tag(self, *, actor: User, tag_id: UUID) -> None:
        """Archive a metadata tag, preserving existing document assignments."""
        tag = await self._get_tag_or_404(actor, tag_id)
        await self.tag_repo.update(tag, is_active=False)
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.metadata_tag_archived",
            target_type="kb_metadata_tag",
            target_id=tag.id,
            metadata={"slug": tag.slug, "label": tag.label},
        )
        await self.session.commit()

    async def resolve_document_metadata(
        self,
        *,
        organization_id: UUID,
        collection_id: UUID,
        tag_slugs: list[str],
        existing_metadata: dict[str, Any] | None = None,
        existing_document: KBDocument | None = None,
    ) -> ResolvedDocumentMetadata:
        """Validate collection/tags and compose canonical KB-service metadata."""
        await self.ensure_defaults(organization_id)
        collection = await self.collection_repo.get_for_organization(
            organization_id=organization_id,
            collection_id=collection_id,
            active_only=True,
        )
        if collection is None:
            raise NotFoundError("KB collection", str(collection_id))

        tags = await self._resolve_tags(
            organization_id=organization_id,
            tag_slugs=tag_slugs,
            existing_document=existing_document,
        )
        return ResolvedDocumentMetadata(
            collection=collection,
            tags=tags,
            metadata_tags=compose_document_metadata(
                collection=collection,
                tags=tags,
                existing_metadata=existing_metadata,
            ),
        )

    async def _resolve_tags(
        self,
        *,
        organization_id: UUID,
        tag_slugs: list[str],
        existing_document: KBDocument | None = None,
    ) -> list[KBMetadataTag]:
        normalized = normalize_tag_slugs(tag_slugs)
        if len(normalized) != len(tag_slugs):
            raise ValidationError("Metadata tags must not contain duplicates")
        rows = await self.tag_repo.list_by_slugs(
            organization_id=organization_id,
            slugs=normalized,
        )
        row_by_slug = {row.slug: row for row in rows}
        missing = [slug for slug in normalized if slug not in row_by_slug]
        if missing:
            raise ValidationError(f"Unknown metadata tags: {', '.join(missing)}")

        existing_slugs = {
            link.tag.slug
            for link in (existing_document.tag_links if existing_document else [])
        }
        archived = [
            slug
            for slug in normalized
            if not row_by_slug[slug].is_active and slug not in existing_slugs
        ]
        if archived:
            raise ValidationError(f"Archived metadata tags cannot be added: {', '.join(archived)}")
        return [row_by_slug[slug] for slug in normalized]

    async def _get_tag_or_404(self, actor: User, tag_id: UUID) -> KBMetadataTag:
        tag = await self.tag_repo.get_for_organization(
            organization_id=actor.organization_id,
            tag_id=tag_id,
        )
        if tag is None:
            raise NotFoundError("KB metadata tag", str(tag_id))
        return tag

    async def _unique_collection_slug(self, organization_id: UUID, title: str) -> str:
        base = slugify(title)
        if not base:
            raise ValidationError("Collection title must contain letters or numbers")
        candidate = base
        suffix = 2
        while await self.collection_repo.get_by_slug(
            organization_id=organization_id,
            slug=candidate,
        ):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    async def _next_collection_sort_order(self, organization_id: UUID) -> int:
        collections = await self.collection_repo.list_by_organization(
            organization_id,
            active_only=False,
        )
        return (max((item.sort_order for item in collections), default=0) + 10)

    async def _next_tag_sort_order(self, organization_id: UUID) -> int:
        tags = await self.tag_repo.list_by_organization(
            organization_id,
            active_only=False,
        )
        return (max((item.sort_order for item in tags), default=0) + 10)


def compose_document_metadata(
    *,
    collection: KBCollection,
    tags: list[KBMetadataTag],
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose the KB-service compatibility metadata payload."""
    metadata = {
        key: value
        for key, value in dict(existing_metadata or {}).items()
        if key not in MANAGED_METADATA_KEYS
    }
    tag_labels = [tag.label for tag in tags]
    metadata.update(
        {
            "collection": collection.slug,
            "collection_title": collection.title,
            "tag_slugs": [tag.slug for tag in tags],
            "tags": tag_labels,
            "topics": [collection.title, *tag_labels],
        }
    )
    return metadata


def normalize_tag_slugs(tag_slugs: list[str]) -> list[str]:
    """Normalize tag slugs from API requests."""
    return [slug.strip().lower() for slug in tag_slugs if slug.strip()]


def slugify(value: str) -> str:
    """Generate a stable URL-safe slug from a user-facing label."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-")


def kb_collection_to_response(collection: KBCollection) -> KBCollectionResponse:
    """Map a KB collection ORM row to a DTO."""
    return KBCollectionResponse.model_validate(collection)


def kb_metadata_tag_to_response(tag: KBMetadataTag) -> KBMetadataTagResponse:
    """Map a KB metadata tag ORM row to a DTO."""
    return KBMetadataTagResponse.model_validate(tag)
