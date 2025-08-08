from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ydrpolicy.backend.database.models import User
from ydrpolicy.backend.database.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for working with User models."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.

        Args:
            username: The username to look up

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email.

        Args:
            email: The email to look up

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(func.lower(User.email) == email.lower())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all active users with pagination.

        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return

        Returns:
            List of active users
        """
        stmt = select(User).where(User.is_active == True).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_admin_users(self) -> List[User]:
        """
        Get all admin users.

        Returns:
            List of admin users
        """
        stmt = select(User).where(User.is_admin == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def authenticate(self, username: str, hashed_password: str) -> Optional[User]:
        """
        Authenticate a user by username and password.

        NOTE: This function expects the password to be already hashed.
        Password hashing should be done at the service layer, not in the repository.

        Args:
            username: Username to authenticate
            hashed_password: Hashed password to check

        Returns:
            User if authentication successful, None otherwise
        """
        user = await self.get_by_username(username)
        if not user:
            return None

        if not user.is_active:
            return None

        if user.hashed_password != hashed_password:
            return None

        return user
