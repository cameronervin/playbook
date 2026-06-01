"""Repository for Example data access.

Demonstrates the repository pattern: all DB access goes through here, using
SQLAlchemy 2.0 `select()` (never `query()`), injected via FastAPI `Depends()`.
"""

from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.example import Example


class ExampleRepository:
    """CRUD operations for the Example model."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get(self, example_id: UUID) -> Example | None:
        result = await self.session.execute(
            select(Example).where(Example.id == example_id)
        )
        return result.scalar_one_or_none()

    async def list(self, status: str | None = None) -> list[Example]:
        stmt = select(Example).order_by(Example.created_at.desc())
        if status is not None:
            stmt = stmt.where(Example.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> Example:
        example = Example(**data)
        self.session.add(example)
        await self.session.commit()
        await self.session.refresh(example)
        return example

    async def update(self, example_id: UUID, data: dict) -> Example | None:
        example = await self.get(example_id)
        if not example:
            return None
        for key, value in data.items():
            setattr(example, key, value)
        await self.session.commit()
        await self.session.refresh(example)
        return example

    async def delete(self, example_id: UUID) -> bool:
        example = await self.get(example_id)
        if not example:
            return False
        await self.session.delete(example)
        await self.session.commit()
        return True
