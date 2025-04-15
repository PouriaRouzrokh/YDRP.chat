# ydrpolicy/backend/routers/chat.py
"""
API Router for chat interactions with the YDR Policy Agent, including history and management.
"""
import asyncio
import json  # Needed for tool call input parsing
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Annotated  # Added types and Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status  # Added status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession  # Added AsyncSession

from ydrpolicy.backend.config import config

# Import necessary schemas
from ydrpolicy.backend.schemas.chat import (
    ChatRequest,
    ChatSummary,
    MessageSummary,
    StreamChunk,
    # Specific data schemas for StreamChunk payload (Optional but good for clarity)
    ErrorData,
    StreamChunkData,
    ChatInfoData,
    TextDeltaData,
    ToolCallData,
    ToolOutputData,
    StatusData,
    ChatRenameRequest, # Added
    ActionResponse, # Added
)
from ydrpolicy.backend.services.chat_service import ChatService

# Correctly import the dependency function that yields the session
from ydrpolicy.backend.database.engine import get_session

# Import Repositories needed for history
from ydrpolicy.backend.database.repository.chats import ChatRepository
from ydrpolicy.backend.database.repository.messages import MessageRepository

# Import the authentication dependency and User model for typing
from ydrpolicy.backend.dependencies import get_current_active_user
from ydrpolicy.backend.database.models import User


# Initialize logger
logger = logging.getLogger(__name__)


# --- Dependency for ChatService ---
def get_chat_service() -> ChatService:
    """FastAPI dependency to get the ChatService instance."""
    # Assuming ChatService manages its own sessions internally when processing streams
    return ChatService(use_mcp=True)


# --- Router Setup ---
router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


# --- Streaming Endpoint ---
@router.post(
    "/stream",
    # No response_model for StreamingResponse
    summary="Initiate or continue a streaming chat session",
    description=(
        "Send a user message and optionally a chat_id to continue an existing conversation. "
        "If chat_id is null, a new chat session is created. Streams back responses including "
        "text deltas, tool usage, status updates, and chat info (like the new chat_id)."
        " Requires authentication."
    ),
    response_description="A stream of Server-Sent Events (SSE). Each event has a 'data' field containing a JSON-encoded StreamChunk.",
    responses={
        200: {"content": {"text/event-stream": {}}},
        401: {"description": "Authentication required"},
        403: {"description": "User ID in request body mismatch"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def stream_chat(
    request: ChatRequest = Body(...),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
):
    """
    Handles streaming chat requests with history persistence.
    Requires authentication. User ID in request body must match authenticated user.
    """
    if request.user_id != current_user.id:
        logger.warning(f"User ID mismatch: Token user ID {current_user.id} != Request body user ID {request.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User ID in request does not match authenticated user."
        )

    logger.info(
        f"API: Received chat stream request for user {current_user.id} (authenticated), chat {request.chat_id}: {request.message[:100]}..."
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in chat_service.process_user_message_stream(
                user_id=current_user.id, message=request.message, chat_id=request.chat_id
            ):
                if hasattr(chunk, "type") and hasattr(chunk, "data"):
                    json_chunk = chunk.model_dump_json(exclude_unset=True)
                    yield f"data: {json_chunk}\n\n"
                    await asyncio.sleep(0.01)
                else:
                    logger.error(f"Invalid chunk received from service: {chunk!r}")

            logger.info(
                f"API: Finished streaming response for user {current_user.id}, chat {request.chat_id or 'new'}."
            )

        except Exception as e:
            logger.error(
                f"Error during stream event generation for user {current_user.id}, chat {request.chat_id}: {e}",
                exc_info=True,
            )
            try:
                error_payload = ErrorData(message=f"Streaming generation failed: {str(e)}")
                if hasattr(chat_service, "_create_stream_chunk"):
                    error_chunk = chat_service._create_stream_chunk("error", error_payload)
                else:
                    error_chunk = StreamChunk(type="error", data=StreamChunkData(**error_payload.model_dump()))
                yield f"data: {error_chunk.model_dump_json()}\n\n"
            except Exception as yield_err:
                logger.error(f"Failed even to yield error chunk: {yield_err}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- List User Chats Endpoint ---
@router.get(
    "",
    response_model=List[ChatSummary],
    summary="List chat sessions for the current user",
    description=(
        "Retrieves a list of chat sessions belonging to the authenticated user, "
        "ordered by the most recently updated. By default, only active (non-archived) chats are returned."
    ),
    response_description="A list of chat session summaries.",
    responses={401: {"description": "Authentication required"}, 500: {"description": "Internal Server Error"}},
)
async def list_user_chats(
    archived: bool = Query(False, description="Set to true to list archived chats instead of active ones."), # Added parameter
    skip: int = Query(0, ge=0, description="Number of chat sessions to skip (for pagination)."),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of chat sessions to return."),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Fetches a paginated list of chat summaries for the authenticated user,
    filtered by archived status.
    """
    status_str = "archived" if archived else "active"
    logger.info(
        f"API: Received request to list {status_str} chats for user {current_user.id} (authenticated) (skip={skip}, limit={limit})."
    )
    try:
        chat_repo = ChatRepository(session)
        # Pass the archived status to the repository method
        chats = await chat_repo.get_chats_by_user(user_id=current_user.id, skip=skip, limit=limit, archived=archived)
        return chats
    except Exception as e:
        logger.error(f"Error fetching {status_str} chats for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve chat list.")


# --- Get Messages for a Chat Endpoint ---
@router.get(
    "/{chat_id}/messages",
    response_model=List[MessageSummary],
    summary="Get messages for a specific chat session",
    description="Retrieves the messages for a specific chat session owned by the authenticated user, ordered chronologically.",
    response_description="A list of messages within the chat session.",
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "User not authorized to access this chat"},
        404: {"description": "Chat session not found"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_chat_messages(
    chat_id: int,
    skip: int = Query(0, ge=0, description="Number of messages to skip (for pagination)."),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of messages to return."),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Fetches a paginated list of messages for a specific chat session,
    ensuring the user owns the chat.
    """
    logger.info(
        f"API: Received request for messages in chat {chat_id} for user {current_user.id} (authenticated) (skip={skip}, limit={limit})."
    )
    try:
        chat_repo = ChatRepository(session)
        msg_repo = MessageRepository(session)

        chat = await chat_repo.get_by_user_and_id(chat_id=chat_id, user_id=current_user.id)
        if not chat:
            logger.warning(f"Chat {chat_id} not found or not owned by user {current_user.id}.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

        messages = await msg_repo.get_by_chat_id_ordered(chat_id=chat_id, limit=None)
        paginated_messages = messages[skip : skip + limit]
        return paginated_messages
    except Exception as e:
        logger.error(f"Error fetching messages for chat {chat_id}, user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve chat messages."
        )


# --- NEW: Rename Chat Endpoint ---
@router.patch(
    "/{chat_id}/rename",
    response_model=ChatSummary,
    summary="Rename a chat session",
    description="Updates the title of a specific chat session owned by the authenticated user.",
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "User not authorized to modify this chat"},
        404: {"description": "Chat session not found"},
        422: {"description": "Validation Error (e.g., empty title)"},
        500: {"description": "Internal Server Error"},
    },
)
async def rename_chat_session(
    chat_id: int,
    request: ChatRenameRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Renames a specific chat session belonging to the authenticated user.
    """
    logger.info(f"API: User {current_user.id} attempting to rename chat {chat_id} to '{request.new_title}'.")
    try:
        chat_repo = ChatRepository(session)
        updated_chat = await chat_repo.update_chat_title(
            chat_id=chat_id, user_id=current_user.id, new_title=request.new_title
        )

        if not updated_chat:
            # get_by_user_and_id check is done within update_chat_title
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found or not owned by user.")

        # Commit the session changes implicitly by exiting the 'with' block in get_session
        return updated_chat # Pydantic will convert to ChatSummary

    except Exception as e:
        logger.error(f"Error renaming chat {chat_id} for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to rename chat session.")


# --- NEW: Archive Chat Endpoint ---
@router.patch(
    "/{chat_id}/archive",
    response_model=ChatSummary,
    summary="Archive a chat session",
    description="Marks a specific chat session owned by the authenticated user as archived.",
    responses={
        200: {"description": "Chat successfully archived"},
        401: {"description": "Authentication required"},
        403: {"description": "User not authorized to modify this chat"},
        404: {"description": "Chat session not found"},
        500: {"description": "Internal Server Error"},
    },
)
async def archive_chat_session(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Archives a specific chat session belonging to the authenticated user.
    """
    logger.info(f"API: User {current_user.id} attempting to archive chat {chat_id}.")
    try:
        chat_repo = ChatRepository(session)
        updated_chat = await chat_repo.archive_chat(
            chat_id=chat_id, user_id=current_user.id, archive=True # Set archive flag to True
        )

        if not updated_chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found or not owned by user.")

        return updated_chat

    except Exception as e:
        logger.error(f"Error archiving chat {chat_id} for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to archive chat session.")


# --- NEW: Unarchive Chat Endpoint ---
@router.patch(
    "/{chat_id}/unarchive",
    response_model=ChatSummary,
    summary="Unarchive a chat session",
    description="Marks a specific chat session owned by the authenticated user as active (not archived).",
    responses={
        200: {"description": "Chat successfully unarchived"},
        401: {"description": "Authentication required"},
        403: {"description": "User not authorized to modify this chat"},
        404: {"description": "Chat session not found"},
        500: {"description": "Internal Server Error"},
    },
)
async def unarchive_chat_session(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Unarchives a specific chat session belonging to the authenticated user.
    """
    logger.info(f"API: User {current_user.id} attempting to unarchive chat {chat_id}.")
    try:
        chat_repo = ChatRepository(session)
        updated_chat = await chat_repo.archive_chat(
            chat_id=chat_id, user_id=current_user.id, archive=False # Set archive flag to False
        )

        if not updated_chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found or not owned by user.")

        return updated_chat

    except Exception as e:
        logger.error(f"Error unarchiving chat {chat_id} for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to unarchive chat session.")


# --- NEW: Archive All Chats Endpoint ---
@router.post(
    "/archive-all",
    response_model=ActionResponse,
    summary="Archive all active chat sessions for the current user",
    description="Marks all active (non-archived) chat sessions for the authenticated user as archived.",
    responses={
        200: {"description": "All active chats successfully archived"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal Server Error"},
    },
)
async def archive_all_user_chats(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Archives all active chat sessions for the authenticated user.
    """
    logger.warning(f"API: User {current_user.id} attempting to archive ALL active chats.")
    try:
        chat_repo = ChatRepository(session)
        archived_count = await chat_repo.archive_all_chats(user_id=current_user.id)

        # Commit the changes
        # await session.commit() # Handled by get_session context manager

        return ActionResponse(message=f"Successfully archived {archived_count} active chat session(s).", count=archived_count)

    except Exception as e:
        logger.error(f"Error archiving all chats for user {current_user.id}: {e}", exc_info=True)
        # await session.rollback() # Handled by get_session context manager
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to archive all chat sessions.")