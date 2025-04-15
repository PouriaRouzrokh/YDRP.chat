# ydrpolicy/backend/database/repository/chats.py
"""
Repository for database operations related to Chat models.
"""
import logging
from typing import Optional, List

# *** ADD func import ***
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ydrpolicy.backend.database.models import Chat, User
from ydrpolicy.backend.database.repository.base import BaseRepository

# Initialize logger
logger = logging.getLogger(__name__)


class ChatRepository(BaseRepository[Chat]):
    """Repository for managing Chat objects in the database."""

    def __init__(self, session: AsyncSession):
        """
        Initializes the ChatRepository.

        Args:
            session: The SQLAlchemy async session.
        """
        super().__init__(session, Chat)
        logger.debug("ChatRepository initialized.")

    async def get_by_user_and_id(self, chat_id: int, user_id: int) -> Optional[Chat]:
        """
        Retrieves a specific chat by its ID, ensuring it belongs to the specified user.

        Args:
            chat_id: The ID of the chat to retrieve.
            user_id: The ID of the user who owns the chat.

        Returns:
            The Chat object if found and owned by the user, otherwise None.
        """
        logger.debug(f"Attempting to retrieve chat ID {chat_id} for user ID {user_id}.")
        stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        result = await self.session.execute(stmt)
        chat = result.scalars().first()
        if chat:
            logger.debug(f"Found chat ID {chat_id} belonging to user ID {user_id}.")
        else:
            logger.warning(f"Chat ID {chat_id} not found or does not belong to user ID {user_id}.")
        return chat

    async def get_chats_by_user(
        self, user_id: int, skip: int = 0, limit: int = 100, archived: bool = False
    ) -> List[Chat]:
        """
        Retrieves a list of chats belonging to a specific user, ordered by update time.
        Can optionally filter for archived chats.

        Args:
            user_id: The ID of the user whose chats to retrieve.
            skip: Number of chats to skip for pagination.
            limit: Maximum number of chats to return.
            archived: If True, retrieves archived chats; otherwise retrieves active chats (default).

        Returns:
            A list of Chat objects.
        """
        status = "archived" if archived else "active"
        logger.debug(f"Retrieving {status} chats for user ID {user_id} (limit={limit}, skip={skip}).")
        stmt = (
            select(Chat)
            .where(Chat.user_id == user_id, Chat.is_archived == archived)  # Filter by archived status
            .order_by(Chat.updated_at.desc())
            .offset(skip)
            .limit(limit)
            # Optionally load messages count or first message for preview later
            # .options(selectinload(Chat.messages)) # Be careful loading all messages
        )
        result = await self.session.execute(stmt)
        chats = list(result.scalars().all())
        logger.debug(f"Found {len(chats)} {status} chats for user ID {user_id}.")
        return chats

    async def create_chat(self, user_id: int, title: Optional[str] = None) -> Chat:
        """
        Creates a new chat session for a user.

        Args:
            user_id: The ID of the user creating the chat.
            title: An optional title for the chat session.

        Returns:
            The newly created Chat object.

        Raises:
            ValueError: If the associated user_id does not exist.
        """
        logger.info(f"Creating new chat for user ID {user_id} with title '{title}'.")
        # Optional: Verify user exists first
        user_check = await self.session.get(User, user_id)
        if not user_check:
            logger.error(f"Cannot create chat: User with ID {user_id} not found.")
            raise ValueError(f"User with ID {user_id} not found.")

        new_chat = Chat(user_id=user_id, title=title)
        chat = await self.create(new_chat)  # Uses BaseRepository.create
        logger.info(f"SUCCESS: Successfully created chat ID {chat.id} for user ID {user_id}.")
        return chat

    async def update_chat_title(self, chat_id: int, user_id: int, new_title: str) -> Optional[Chat]:
        """
        Updates the title of a specific chat, verifying ownership.

        Args:
            chat_id: The ID of the chat to update.
            user_id: The ID of the user attempting the update.
            new_title: The new title for the chat.

        Returns:
            The updated Chat object if successful, None otherwise.
        """
        logger.info(f"Attempting to update title for chat ID {chat_id} (user ID {user_id}) to '{new_title}'.")
        chat = await self.get_by_user_and_id(chat_id=chat_id, user_id=user_id)
        if not chat:
            logger.warning(f"Cannot update title: Chat ID {chat_id} not found for user ID {user_id}.")
            return None

        chat.title = new_title
        # updated_at is handled automatically by the model definition's onupdate,
        # but we need to ensure the session knows the object changed.
        # *** ADD THIS LINE ***
        self.session.add(chat)  # Explicitly mark the object as potentially dirty
        await self.session.flush()
        await self.session.commit()  # Explicitly commit the transaction
        await self.session.refresh(chat)
        logger.info(f"SUCCESS: Successfully updated title for chat ID {chat_id}.")
        return chat

    async def archive_chat(self, chat_id: int, user_id: int, archive: bool = True) -> Optional[Chat]:
        """
        Archives or unarchives a specific chat, verifying ownership.

        Args:
            chat_id: The ID of the chat to update.
            user_id: The ID of the user attempting the update.
            archive: True to archive, False to unarchive.

        Returns:
            The updated Chat object if successful, None otherwise.
        """
        action = "archive" if archive else "unarchive"
        logger.info(f"Attempting to {action} chat ID {chat_id} (user ID {user_id}).")
        chat = await self.get_by_user_and_id(chat_id=chat_id, user_id=user_id)
        if not chat:
            logger.warning(f"Cannot {action}: Chat ID {chat_id} not found for user ID {user_id}.")
            return None

        if chat.is_archived == archive:
            status = "already archived" if archive else "already active"
            logger.info(f"Chat ID {chat_id} is {status}. No change needed.")
            return chat  # Return the chat as is

        chat.is_archived = archive
        # updated_at is handled automatically by the model definition's onupdate,
        # but we need to ensure the session knows the object changed.
        # *** ADD THIS LINE ***
        self.session.add(chat)  # Explicitly mark the object as potentially dirty
        await self.session.flush()
        await self.session.commit()  # Explicitly commit the transaction
        await self.session.refresh(chat)
        logger.info(f"SUCCESS: Successfully {action}d chat ID {chat_id}.")
        return chat

    async def archive_all_chats(self, user_id: int) -> int:
        """
        Archives all active chats for a specific user.

        Args:
            user_id: The ID of the user whose chats to archive.

        Returns:
            The number of chats that were archived.
        """
        logger.warning(f"Attempting to archive ALL active chats for user ID {user_id}.")
        stmt = (
            update(Chat)
            .where(Chat.user_id == user_id, Chat.is_archived == False)  # Only archive active chats
            .values(is_archived=True, updated_at=func.now())  # Explicitly set updated_at for bulk update
        )
        result = await self.session.execute(stmt)
        archived_count = result.rowcount
        # *** Flush is needed here for bulk update ***
        await self.session.flush()  # Ensure changes are flushed before commit
        await self.session.commit()  # Explicitly commit the transaction
        logger.info(f"SUCCESS: Archived {archived_count} chats for user ID {user_id}.")
        return archived_count

    async def delete_chat(self, chat_id: int, user_id: int) -> bool:
        """
        Deletes a specific chat and its associated messages, verifying ownership.
        Relies on cascade delete for messages.

        Args:
            chat_id: The ID of the chat to delete.
            user_id: The ID of the user attempting the deletion.

        Returns:
            True if the chat was deleted, False otherwise.
        """
        logger.warning(f"Attempting to delete chat ID {chat_id} for user ID {user_id}.")
        chat = await self.get_by_user_and_id(chat_id=chat_id, user_id=user_id)
        if not chat:
            logger.error(f"Cannot delete: Chat ID {chat_id} not found for user ID {user_id}.")
            return False

        try:
            await self.session.delete(chat)
            await self.session.flush()
            await self.session.commit()  # Explicitly commit the transaction
            logger.info(f"SUCCESS: Successfully deleted chat ID {chat_id} and its messages.")
            return True
        except Exception as e:
            logger.error(f"Error deleting chat ID {chat_id}: {e}", exc_info=True)
            # Rollback should be handled by the session context manager
            return False
