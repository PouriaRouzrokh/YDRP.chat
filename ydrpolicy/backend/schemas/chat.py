# ydrpolicy/backend/schemas/chat.py
"""
Pydantic models for chat API requests and responses, including history handling.
"""
from datetime import datetime  # Import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict  # Import ConfigDict


class ChatRequest(BaseModel):
    """Request model for the streaming chat endpoint."""

    user_id: int = Field(..., description="The ID of the user initiating the chat request.")
    message: str = Field(..., description="The user's current message to the chat agent.")
    chat_id: Optional[int] = Field(
        None, description="The ID of an existing chat session to continue. If None, a new chat will be created."
    )


# --- StreamChunk definition ---
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
        ..., description="Type of the chunk (e.g., 'text_delta', 'tool_call', 'chat_info', 'error', 'status')."
    )
    data: StreamChunkData = Field(..., description="The actual data payload for the chunk.")


# --- Specific data models for StreamChunk payloads ---
class ChatInfoData(BaseModel):
    chat_id: int = Field(..., description="The ID of the chat session (new or existing).")
    title: Optional[str] = Field(None, description="The title of the chat session.")


class TextDeltaData(BaseModel):
    delta: str = Field(..., description="The text delta.")


class ToolCallData(BaseModel):
    id: str = Field(..., description="The unique ID for this tool call.")
    name: str = Field(..., description="The name of the tool being called.")
    input: Dict[str, Any] = Field(..., description="The arguments passed to the tool.")


class ToolOutputData(BaseModel):
    tool_call_id: str = Field(..., description="The ID of the corresponding tool call.")
    output: Any = Field(..., description="The result returned by the tool.")


class ErrorData(BaseModel):
    message: str = Field(..., description="Error message details.")


class StatusData(BaseModel):
    status: str = Field(..., description="The final status of the agent run (e.g., 'complete', 'error').")
    chat_id: Optional[int] = Field(None, description="The ID of the chat session, included on final status.")


# --- NEW Schemas for History Endpoints ---


class ChatSummary(BaseModel):
    """Summary information for a chat session, used in listings."""

    id: int = Field(..., description="Unique identifier for the chat session.")
    title: Optional[str] = Field(None, description="Title of the chat session.")
    created_at: datetime = Field(..., description="Timestamp when the chat was created.")
    updated_at: datetime = Field(..., description="Timestamp when the chat was last updated (last message).")

    # Enable ORM mode to allow creating instances from SQLAlchemy models
    model_config = ConfigDict(from_attributes=True)


class MessageSummary(BaseModel):
    """Represents a single message within a chat history."""

    id: int = Field(..., description="Unique identifier for the message.")
    role: str = Field(..., description="Role of the message sender ('user' or 'assistant').")
    content: str = Field(..., description="Text content of the message.")
    created_at: datetime = Field(..., description="Timestamp when the message was created.")
    # Optional: Add tool_usages here later if needed by frontend history display
    # tool_usages: Optional[List[Dict[str, Any]]] = None

    # Enable ORM mode
    model_config = ConfigDict(from_attributes=True)
