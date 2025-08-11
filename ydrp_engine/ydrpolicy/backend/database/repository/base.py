from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, cast

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ydrpolicy.backend.database.models import Base

# Type variable for ORM models
ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Base repository class with common CRUD operations for all models.

    This class uses SQLAlchemy 2.0 style for async operations.
    """

    def __init__(self, session: AsyncSession, model_class: Type[ModelType]):
        """
        Initialize the repository with a session and model class.

        Args:
            session: SQLAlchemy async session
            model_class: The SQLAlchemy model class this repository handles
        """
        self.session = session
        self.model_class = model_class

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Get a record by its ID.

        Args:
            id: The ID of the record to retrieve

        Returns:
            The record if found, None otherwise
        """
        stmt = select(self.model_class).where(self.model_class.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Get all records with pagination.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of records
        """
        stmt = select(self.model_class).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj_in: ModelType) -> ModelType:
        """
        Create a new record.

        Args:
            obj_in: The model instance to create

        Returns:
            The created model instance with ID populated
        """
        self.session.add(obj_in)
        await self.session.flush()
        await self.session.refresh(obj_in)
        return obj_in

    async def update(self, id: int, obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            id: The ID of the record to update
            obj_in: Dictionary of fields to update

        Returns:
            The updated model instance if found, None otherwise
        """
        stmt = (
            update(self.model_class)
            .where(self.model_class.id == id)
            .values(**obj_in)
            .returning(self.model_class)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalars().first()

    async def delete(self, id: int) -> bool:
        """
        Delete a record by ID.

        Args:
            id: The ID of the record to delete

        Returns:
            True if the record was deleted, False if not found
        """
        stmt = delete(self.model_class).where(self.model_class.id == id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def delete_all(self) -> int:
        """
        Delete all records.

        Returns:
            Number of records deleted
        """
        stmt = delete(self.model_class)
        result = await self.session.execute(stmt)
        return result.rowcount

    async def count(self) -> int:
        """
        Count all records.

        Returns:
            Total number of records
        """
        stmt = select(self.model_class)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())
