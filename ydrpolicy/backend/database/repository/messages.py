# ydrpolicy/backend/database/repository/messages.py
"""
Repository for database operations related to Message and ToolUsage models.
"""
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ydrpolicy.backend.database.models import Message, ToolUsage, Chat
from ydrpolicy.backend.database.repository.base import BaseRepository

# Initialize logger
logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository[Message]):
    """Repository for managing Message and ToolUsage objects."""

    def __init__(self, session: AsyncSession):
        """
        Initializes the MessageRepository.

        Args:
            session: The SQLAlchemy async session.
        """
        super().__init__(session, Message)
        logger.debug("MessageRepository initialized.")

    async def get_by_chat_id_ordered(
        self, chat_id: int, limit: Optional[int] = None
    ) -> List[Message]:
        """
        Retrieves all messages for a given chat ID, ordered by creation time (oldest first).

        Args:
            chat_id: The ID of the chat session.
            limit: Optional limit on the number of messages to retrieve (retrieves latest if limited).

        Returns:
            A list of Message objects, ordered chronologically.
        """
        logger.debug(
            f"Retrieving messages for chat ID {chat_id}"
            + (f" (limit={limit})" if limit else "")
        )
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .options(selectinload(Message.tool_usages))  # Eager load tool usage data
            .order_by(Message.created_at.asc())  # Ascending for chronological order
        )
        # If limit is applied, usually you want the *most recent* N messages for context
        if limit:
            # Subquery approach or reverse order + limit then reverse in Python might be needed
            # For simplicity, let's re-order and limit if limit is provided
            stmt = stmt.order_by(Message.created_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())

        # If we limited and got descending order, reverse back to ascending
        if limit:
            messages.reverse()

        logger.debug(f"Found {len(messages)} messages for chat ID {chat_id}.")
        return messages

    async def create_message(self, chat_id: int, role: str, content: str) -> Message:
        """
        Creates a new message within a chat session.

        Args:
            chat_id: The ID of the chat this message belongs to.
            role: The role of the message sender ('user' or 'assistant').
            content: The text content of the message.

        Returns:
            The newly created Message object.

        Raises:
            ValueError: If the associated chat_id does not exist.
        """
        logger.debug(f"Creating new message for chat ID {chat_id} (role: {role}).")
        # Optional: Verify chat exists first
        chat_check = await self.session.get(Chat, chat_id)
        if not chat_check:
            logger.error(f"Cannot create message: Chat with ID {chat_id} not found.")
            raise ValueError(f"Chat with ID {chat_id} not found.")

        new_message = Message(chat_id=chat_id, role=role, content=content)
        message = await self.create(new_message)  # Uses BaseRepository.create
        logger.debug(
            f"Successfully created message ID {message.id} for chat ID {chat_id}."
        )

        # Update the parent chat's updated_at timestamp
        # SQLAlchemy might handle this if relationship is configured, but explicit update is safer
        chat_check.updated_at = message.created_at  # Use message creation time
        self.session.add(chat_check)
        await self.session.flush([chat_check])  # Flush only the chat update

        return message

    async def create_tool_usage_for_message(
        self,
        message_id: int,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
    ) -> ToolUsage:
        """
        Creates a ToolUsage record associated with a specific assistant message.

        Args:
            message_id: The ID of the assistant Message this tool usage relates to.
            tool_name: The name of the tool that was called.
            tool_input: The input parameters passed to the tool (as a dict).
            tool_output: The output/result received from the tool (as a dict, optional).
            execution_time: Time taken for the tool execution in seconds (optional).

        Returns:
            The newly created ToolUsage object.

        Raises:
            ValueError: If the associated message_id does not exist or does not belong to an assistant.
        """
        logger.debug(
            f"Creating tool usage record for message ID {message_id} (tool: {tool_name})."
        )
        # Optional: Verify message exists and role is 'assistant'
        msg_check = await self.session.get(Message, message_id)
        if not msg_check:
            logger.error(
                f"Cannot create tool usage: Message with ID {message_id} not found."
            )
            raise ValueError(f"Message with ID {message_id} not found.")
        if msg_check.role != "assistant":
            logger.error(
                f"Cannot create tool usage: Message ID {message_id} belongs to role '{msg_check.role}', not 'assistant'."
            )
            raise ValueError(
                f"Tool usage can only be associated with 'assistant' messages (message ID {message_id} has role '{msg_check.role}')."
            )

        new_tool_usage = ToolUsage(
            message_id=message_id,
            tool_name=tool_name,
            input=tool_input,
            output=tool_output,
            execution_time=execution_time,
        )
        self.session.add(new_tool_usage)
        await self.session.flush()
        await self.session.refresh(new_tool_usage)
        logger.debug(
            f"Successfully created tool usage ID {new_tool_usage.id} for message ID {message_id}."
        )
        return new_tool_usage
