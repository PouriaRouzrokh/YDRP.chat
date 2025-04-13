# ydrpolicy/backend/schemas/chat.py
"""
Pydantic models for chat API requests and responses, including history handling.
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for the streaming chat endpoint."""

    user_id: int = Field(..., description="The ID of the user initiating the chat request.")
    message: str = Field(..., description="The user's current message to the chat agent.")
    chat_id: Optional[int] = Field(
        None, description="The ID of an existing chat session to continue. If None, a new chat will be created."
    )
    # Removed chat_history: History will be loaded from the database based on chat_id.


# --- StreamChunk definition remains the same, but we'll use specific 'type' values ---
# --- for history-related events like 'chat_created' ---
class StreamChunkData(BaseModel):
    """Flexible data payload for StreamChunk."""

    # Allow any field, specific validation done by consumer based on type
    class Config:
        extra = "allow"


class StreamChunk(BaseModel):
    """
    Model for a single chunk streamed back to the client via SSE.
    The 'data' field's structure depends on the 'type'.
    """

    type: str = Field(
        ...,
        description="Type of the chunk (e.g., 'text_delta', 'tool_call', 'tool_output', 'chat_info', 'error', 'status').",
    )
    data: StreamChunkData = Field(..., description="The actual data payload for the chunk.")


# Example specific data models for clarity (Optional, but good practice)
class ChatInfoData(BaseModel):
    chat_id: int = Field(..., description="The ID of the chat session (new or existing).")
    title: Optional[str] = Field(None, description="The title of the chat session.")


class TextDeltaData(BaseModel):
    delta: str = Field(..., description="The text delta.")


class ToolCallData(BaseModel):
    id: str = Field(..., description="The unique ID for this tool call.")
    name: str = Field(..., description="The name of the tool being called.")
    # Input might be complex, keeping it Any for flexibility
    input: Dict[str, Any] = Field(..., description="The arguments passed to the tool.")


class ToolOutputData(BaseModel):
    tool_call_id: str = Field(..., description="The ID of the corresponding tool call.")
    # Output might be complex, keeping it Any for flexibility
    output: Any = Field(..., description="The result returned by the tool.")


class ErrorData(BaseModel):
    message: str = Field(..., description="Error message details.")


class StatusData(BaseModel):
    status: str = Field(..., description="The final status of the agent run (e.g., 'complete', 'error').")
    chat_id: Optional[int] = Field(None, description="The ID of the chat session, included on final status.")
