# ydrpolicy/backend/routers/chat.py
"""
API Router for chat interactions with the YDR Policy Agent, including history.
"""
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse

from ydrpolicy.backend.config import config

# Updated schema import
from ydrpolicy.backend.schemas.chat import ChatRequest, StreamChunk
from ydrpolicy.backend.services.chat_service import ChatService
from ydrpolicy.backend.logger import BackendLogger

# Initialize logger
logger = BackendLogger(name=__name__, path=config.LOGGING.FILE)

from ydrpolicy.backend.database.engine import get_async_session # For potential repo injection later

# --- Dependency Injection Refinement (Example) ---
# Option 1: Simple instance creation (as before)
# def get_chat_service() -> ChatService:
#     return ChatService(use_mcp=True)

# Option 2: Injecting dependencies (more robust, requires session dependency)
# async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
#     async with get_async_session() as session:
#         yield session
#
# def get_chat_service(session: AsyncSession = Depends(get_db_session)) -> ChatService:
#     # If ChatService needed session directly or repositories needed injection
#     # chat_repo = ChatRepository(session)
#     # msg_repo = MessageRepository(session)
#     # return ChatService(chat_repo=chat_repo, msg_repo=msg_repo, use_mcp=True)
#     # For now, ChatService uses get_async_session internally, so simple init is fine
#     return ChatService(use_mcp=True)


# --- Router Setup ---
router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

# Use simple dependency for now
def get_chat_service() -> ChatService:
    """FastAPI dependency to get the ChatService instance."""
    return ChatService(use_mcp=True)


@router.post(
    "/stream",
    # response_model=None, # Correct for StreamingResponse
    summary="Initiate or continue a streaming chat session",
    description=(
        "Send a user message and optionally a chat_id to continue an existing conversation. "
        "If chat_id is null, a new chat session is created. Streams back responses including "
        "text deltas, tool usage, status updates, and chat info (like the new chat_id)."
    ),
    response_description="A stream of Server-Sent Events (SSE). Each event has a 'data' field containing a JSON-encoded StreamChunk.",
    responses={
        200: {"content": {"text/event-stream": {}}},
        422: {"description": "Validation Error (e.g., missing user_id)"},
        500: {"description": "Internal Server Error during processing"},
    }
)
async def stream_chat(
    # Use the updated ChatRequest schema
    request: ChatRequest = Body(...),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Handles streaming chat requests with history persistence.
    """
    logger.api(f"Received chat stream request for user {request.user_id}, chat {request.chat_id}: {request.message[:100]}...")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generates SSE formatted JSON strings for each stream chunk."""
        try:
            # Pass user_id, message, and optional chat_id to the service
            async for chunk in chat_service.process_user_message_stream(
                user_id=request.user_id,
                message=request.message,
                chat_id=request.chat_id
            ):
                json_chunk = chunk.model_dump_json(exclude_unset=True)
                yield f"data: {json_chunk}\n\n" # SSE format
                await asyncio.sleep(0.01) # Yield control briefly

            logger.api(f"Finished streaming response for user {request.user_id}, chat {request.chat_id or 'new'}.")
            # Ensure a final "end" event or rely on the status event from the service
            # yield "data: {\"type\": \"stream_end\", \"data\": {\"message\": \"Stream finished\"}}\n\n"

        except Exception as e:
             logger.error(f"Error during stream event generation for user {request.user_id}, chat {request.chat_id}: {e}", exc_info=True)
             error_chunk = StreamChunk(type="error", data={"message": f"Streaming generation failed: {str(e)}"})
             try:
                 yield f"data: {error_chunk.model_dump_json()}\n\n"
             except Exception as yield_err:
                  logger.error(f"Failed even to yield error chunk: {yield_err}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")