# ydrpolicy/backend/routers/chat.py
"""
API Router for chat interactions with the YDR Policy Agent, including history.
"""
import asyncio
import json # Needed for tool call input parsing
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession # Keep this import

from ydrpolicy.backend.config import config
# Import necessary schemas
from ydrpolicy.backend.schemas.chat import (
    ChatRequest,
    ChatSummary,
    ErrorData, # Used by ChatService helper
    MessageSummary,
    StatusData, # Used by ChatService helper
    StreamChunk,
    StreamChunkData, # Used by ChatService helper
    # No need to import the specific data schemas used only internally by ChatService here
)
from ydrpolicy.backend.services.chat_service import ChatService
# *** CORRECTED IMPORT: Use the generator function for dependency injection ***
from ydrpolicy.backend.database.engine import get_session # Import the correct dependency
# Import Repositories needed for history
from ydrpolicy.backend.database.repository.chats import ChatRepository
from ydrpolicy.backend.database.repository.messages import MessageRepository


# Initialize logger
logger = logging.getLogger(__name__)


# --- Placeholder Dependency for Authenticated User ID ---
# In a real application, this would decode a JWT or session cookie
# For now, it just returns a fixed ID for testing.
async def get_current_user_id_placeholder() -> int:
    """Placeholder dependency to simulate getting the current user's ID."""
    # Replace this with your actual authentication logic later
    logger.warning("Using placeholder user ID 1 for authentication.")
    return 1
# -------------------------------------------------------


# --- Dependency for ChatService ---
def get_chat_service() -> ChatService:
    """FastAPI dependency to get the ChatService instance."""
    # Assuming ChatService manages its own sessions internally when processing streams
    return ChatService(use_mcp=True)


# --- Router Setup ---
router = APIRouter(
    prefix="/chat",
    tags=["Chat"], # Keep existing tag
)

# --- Existing Streaming Endpoint ---
@router.post(
    "/stream",
    # No response_model for StreamingResponse
    summary="Initiate or continue a streaming chat session",
    description=(
        "Send a user message and optionally a chat_id to continue an existing conversation. "
        "If chat_id is null, a new chat session is created. Streams back responses including "
        "text deltas, tool usage, status updates, and chat info (like the new chat_id)."
    ),
    response_description="A stream of Server-Sent Events (SSE). Each event has a 'data' field containing a JSON-encoded StreamChunk.",
    responses={
        200: {"content": {"text/event-stream": {}}},
        422: {"description": "Validation Error (e.g., missing user_id in request body)"},
        500: {"description": "Internal Server Error during processing"},
    },
)
async def stream_chat(
    request: ChatRequest = Body(...),
    chat_service: ChatService = Depends(get_chat_service), # ChatService handles its own session for streaming
):
    """
    Handles streaming chat requests with history persistence.
    Requires user_id in the request body. Gets chat_id from body if continuing.
    """
    # Note: user_id validation against auth token should happen here or in ChatService
    logger.info(
        f"API: Received chat stream request for user {request.user_id}, chat {request.chat_id}: {request.message[:100]}..."
    )

    # This internal helper relies on the ChatService correctly yielding StreamChunk objects
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Pass user_id, message, and optional chat_id from request body
            async for chunk in chat_service.process_user_message_stream(
                user_id=request.user_id, message=request.message, chat_id=request.chat_id
            ):
                # Ensure chunk has necessary fields before dumping
                if hasattr(chunk, 'type') and hasattr(chunk, 'data'):
                    json_chunk = chunk.model_dump_json(exclude_unset=True)
                    yield f"data: {json_chunk}\n\n"  # SSE format
                    await asyncio.sleep(0.01) # Yield control briefly
                else:
                    logger.error(f"Invalid chunk received from service: {chunk!r}")

            logger.info(
                f"API: Finished streaming response for user {request.user_id}, chat {request.chat_id or 'new'}."
            )

        except Exception as e:
            logger.error(
                f"Error during stream event generation for user {request.user_id}, chat {request.chat_id}: {e}",
                exc_info=True,
            )
            # Manually create the error chunk structure using the schema helper in ChatService
            error_payload = ErrorData(message=f"Streaming generation failed: {str(e)}")
            error_chunk = chat_service._create_stream_chunk("error", error_payload) # Use helper if accessible, otherwise recreate
            try:
                yield f"data: {error_chunk.model_dump_json()}\n\n"
            except Exception as yield_err:
                logger.error(f"Failed even to yield error chunk: {yield_err}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- NEW Endpoint: List User Chats ---
@router.get(
    "", # GET request to the base /chat prefix
    response_model=List[ChatSummary],
    summary="List chat sessions for the current user",
    description="Retrieves a list of chat sessions belonging to the authenticated user, ordered by the most recently updated.",
    response_description="A list of chat session summaries.",
    responses={
        401: {"description": "Authentication required"},
    }
)
async def list_user_chats(
    skip: int = Query(0, ge=0, description="Number of chat sessions to skip (for pagination)."),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of chat sessions to return."),
    user_id: int = Depends(get_current_user_id_placeholder),
    # *** CORRECTED DEPENDENCY: Use get_session which yields the session ***
    session: AsyncSession = Depends(get_session),
):
    """
    Fetches a paginated list of chat summaries for the authenticated user.
    """
    logger.info(f"API: Received request to list chats for user {user_id} (skip={skip}, limit={limit}).")
    try:
        # Instantiate the repository INSIDE the endpoint, passing the actual session
        chat_repo = ChatRepository(session)
        chats = await chat_repo.get_chats_by_user(user_id=user_id, skip=skip, limit=limit)
        # Pydantic automatically converts Chat models to ChatSummary based on response_model
        return chats
    except Exception as e:
        logger.error(f"Error fetching chats for user {user_id}: {e}", exc_info=True)
        # Rollback is handled by the generator context manager in get_session
        raise HTTPException(status_code=500, detail="Failed to retrieve chat list.")


# --- NEW Endpoint: Get Messages for a Chat ---
@router.get(
    "/{chat_id}/messages",
    response_model=List[MessageSummary],
    summary="Get messages for a specific chat session",
    description="Retrieves the messages for a specific chat session owned by the authenticated user, ordered chronologically.",
    response_description="A list of messages within the chat session.",
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "User not authorized to access this chat"}, # Should be handled by check below
        404: {"description": "Chat session not found"},
    }
)
async def get_chat_messages(
    chat_id: int,
    skip: int = Query(0, ge=0, description="Number of messages to skip (for pagination)."),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of messages to return."),
    user_id: int = Depends(get_current_user_id_placeholder),
    # *** CORRECTED DEPENDENCY: Use get_session which yields the session ***
    session: AsyncSession = Depends(get_session),
):
    """
    Fetches a paginated list of messages for a specific chat session,
    ensuring the user owns the chat.
    """
    logger.info(f"API: Received request for messages in chat {chat_id} for user {user_id} (skip={skip}, limit={limit}).")
    try:
        # Instantiate repositories INSIDE the endpoint with the actual session
        chat_repo = ChatRepository(session)
        msg_repo = MessageRepository(session)

        # First, verify the chat exists and belongs to the user
        chat = await chat_repo.get_by_user_and_id(chat_id=chat_id, user_id=user_id)
        if not chat:
            logger.warning(f"Chat {chat_id} not found or not owned by user {user_id}.")
            raise HTTPException(status_code=404, detail="Chat session not found.")

        # If ownership is confirmed, fetch the messages
        messages = await msg_repo.get_by_chat_id_ordered(chat_id=chat_id, limit=None) # Get all first
        paginated_messages = messages[skip : skip + limit] # Slice for pagination
        # Pydantic converts Message models to MessageSummary based on response_model
        return paginated_messages
    except Exception as e:
        logger.error(f"Error fetching messages for chat {chat_id}, user {user_id}: {e}", exc_info=True)
        # Rollback handled by generator context manager
        raise HTTPException(status_code=500, detail="Failed to retrieve chat messages.")