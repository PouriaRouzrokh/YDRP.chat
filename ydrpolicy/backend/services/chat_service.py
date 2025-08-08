# ydrpolicy/backend/services/chat_service.py
"""
Service layer for handling chat interactions with the Policy Agent,
including database persistence for history using structured input.
Handles errors via exceptions from the agent runner.
Manages MCP connection lifecycle using async context manager.
"""
import asyncio
import contextlib  # For null_async_context
import datetime
import json  # For safe parsing of tool arguments
import logging  # Use standard logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

# Agents SDK imports
from agents import Agent, Runner, RunResult, RunResultStreaming
from agents.exceptions import (
    AgentsException,
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    OutputGuardrailTripwireTriggered,
    UserError,
)
from agents.mcp import MCPServerSse  # For type checking and context management

# Import only the necessary event types from agents.stream_events
from agents.stream_events import (
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)

# OpenAI types
from openai.types.chat import ChatCompletionMessageParam

# Only import the specific response types actually used
from openai.types.responses import ResponseTextDeltaEvent

# Local application imports
from ydrpolicy.backend.agent.policy_agent import create_policy_agent
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.models import Message as DBMessage
from ydrpolicy.backend.database.repository.chats import ChatRepository
from ydrpolicy.backend.database.repository.messages import MessageRepository

# Import all specific data schemas AND the wrapper StreamChunkData
from ydrpolicy.backend.schemas.chat import (
    ChatInfoData,
    ErrorData,
    StatusData,
    StreamChunk,
    StreamChunkData,  # The wrapper
    TextDeltaData,
    ToolCallData,
    ToolOutputData,
)

logger = logging.getLogger(__name__)

# Constants
MAX_HISTORY_MESSAGES = 20  # Max user/assistant message pairs for history context


# Helper dummy async context manager (used when MCP is disabled)
@contextlib.asynccontextmanager
async def null_async_context(*args, **kwargs):
    """A dummy async context manager that does nothing."""
    yield None


class ChatService:
    """
    Handles interactions with the Policy Agent, including history persistence
    and MCP connection management.
    """

    def __init__(self, use_mcp: bool = True):
        """
        Initializes the ChatService.

        Args:
            use_mcp: Whether to enable MCP tool usage. Defaults to True.
        """
        self.use_mcp = use_mcp
        self._agent: Optional[Agent] = None
        self._init_task: Optional[asyncio.Task] = None
        logger.info(f"ChatService initialized (MCP Enabled: {self.use_mcp})")

    async def _initialize_agent(self):
        """Initializes the underlying policy agent if not already done."""
        if self._agent is None:
            logger.info("Initializing Policy Agent for ChatService...")
            try:
                self._agent = await create_policy_agent(use_mcp=self.use_mcp)
                logger.info("Policy Agent initialized successfully in ChatService.")
            except Exception as e:
                logger.error(
                    f"Failed to initialize agent in ChatService: {e}", exc_info=True
                )
                self._agent = None  # Ensure agent is None on failure

    async def get_agent(self) -> Agent:
        """
        Gets the initialized policy agent instance, initializing it if necessary.

        Returns:
            The initialized Agent instance.

        Raises:
            RuntimeError: If agent initialization fails.
        """
        if self._agent is None:
            if self._init_task is None or self._init_task.done():
                # Start initialization task if not already running
                self._init_task = asyncio.create_task(self._initialize_agent())
            await self._init_task  # Wait for initialization to complete
        if self._agent is None:
            # Check again after waiting, raise if still None
            raise RuntimeError("Agent initialization failed. Cannot proceed.")
        return self._agent

    async def _format_history_for_agent(
        self, history: List[DBMessage]
    ) -> List[ChatCompletionMessageParam]:
        """
        Formats database message history into the list format expected by the agent.

        Args:
            history: List of DBMessage objects from the database.

        Returns:
            A list of dictionaries formatted for ChatCompletionMessageParam.
        """
        formatted_messages: List[ChatCompletionMessageParam] = []
        # Limit history to avoid exceeding token limits
        limited_history = history[-(MAX_HISTORY_MESSAGES * 2) :]
        for msg in limited_history:
            if msg.role == "user":
                formatted_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # Basic formatting - just the content.
                # Add tool call representation here if needed by model/SDK for better context.
                formatted_messages.append({"role": "assistant", "content": msg.content})
        logger.debug(
            f"Formatted DB history into {len(formatted_messages)} message dicts."
        )
        return formatted_messages

    def _create_stream_chunk(self, chunk_type: str, payload: Any) -> StreamChunk:
        """
        Creates a StreamChunk, ensuring the data payload is correctly wrapped.

        Args:
            chunk_type: The type of the chunk (e.g., "error", "chat_info").
            payload: The specific Pydantic model instance for the data (e.g., ErrorData(...)).

        Returns:
            A correctly formatted StreamChunk object.
        """
        # Use model_dump() to get dict from Pydantic model, then pass kwargs to StreamChunkData
        payload_dict = (
            payload.model_dump(exclude_unset=True)
            if hasattr(payload, "model_dump")
            else payload
        )
        if not isinstance(payload_dict, dict):
            # Fallback if payload wasn't a Pydantic model or dict
            logger.warning(
                f"Payload for chunk type '{chunk_type}' was not a dict or Pydantic model, wrapping as is."
            )
            payload_dict = {"value": payload_dict}

        return StreamChunk(type=chunk_type, data=StreamChunkData(**payload_dict))

    async def process_user_message_stream(
        self, user_id: int, message: str, chat_id: Optional[int] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Processes a user message using the agent, handling history and DB persistence.
        Manages MCP connection lifecycle using async with. Streams back results.

        Args:
            user_id: The ID of the user sending the message.
            message: The user's message content.
            chat_id: The ID of the chat to continue, or None to start a new chat.

        Yields:
            StreamChunk: Objects representing parts of the agent's response or status.
        """
        logger.info(
            f"Processing message stream for user {user_id}, chat {chat_id}, message: '{message[:100]}...'"
        )
        agent_response_content = ""
        # Use List[Tuple[Any, Any]] since specific item types aren't importable
        tool_calls_data: List[Tuple[Any, Optional[Any]]] = []
        final_status_str: str = "unknown"
        error_message: Optional[str] = None
        processed_chat_id: Optional[int] = chat_id
        chat_title: Optional[str] = None
        run_result_stream: Optional[RunResultStreaming] = None
        agent: Optional[Agent] = None

        try:
            agent = await self.get_agent()  # Get the agent instance

            # Get the MCP server instance if configured
            mcp_server_instance = None
            if self.use_mcp and agent and agent.mcp_servers:
                mcp_server_instance = agent.mcp_servers[0]

            # Use 'async with' to manage the MCP connection lifecycle
            async with (
                mcp_server_instance
                if mcp_server_instance and isinstance(mcp_server_instance, MCPServerSse)
                else null_async_context()
            ) as active_mcp_connection:
                # Check for connection errors if MCP was expected
                if self.use_mcp:
                    if mcp_server_instance and active_mcp_connection is None:
                        error_message = "MCP connection failed during context entry."
                        logger.error(error_message)
                        final_status_str = "error"
                        yield self._create_stream_chunk(
                            "error",
                            ErrorData(
                                message="Could not connect to required tools server."
                            ),
                        )
                        return  # Stop processing
                    elif mcp_server_instance:
                        logger.info(
                            "API Mode: MCP connection established via async context."
                        )

                # --- Proceed with DB operations and agent run INSIDE the context manager ---
                async with get_async_session() as session:
                    chat_repo = ChatRepository(session)
                    msg_repo = MessageRepository(session)

                    # 1. Ensure Chat Session Exists & Load History
                    history_messages: List[DBMessage] = []
                    if processed_chat_id:
                        chat = await chat_repo.get_by_user_and_id(
                            chat_id=processed_chat_id, user_id=user_id
                        )
                        if not chat:
                            error_message = f"Chat ID {processed_chat_id} not found or does not belong to user ID {user_id}."
                            logger.error(error_message)
                            final_status_str = "error"
                            yield self._create_stream_chunk(
                                "error", ErrorData(message=error_message)
                            )
                            return  # Stop processing early
                        history_messages = await msg_repo.get_by_chat_id_ordered(
                            chat_id=processed_chat_id, limit=MAX_HISTORY_MESSAGES * 2
                        )
                        chat_title = chat.title
                        logger.debug(
                            f"Loaded {len(history_messages)} messages for chat ID {processed_chat_id}."
                        )
                        yield self._create_stream_chunk(
                            "chat_info",
                            ChatInfoData(chat_id=processed_chat_id, title=chat_title),
                        )
                    else:
                        new_title = message[:80] + ("..." if len(message) > 80 else "")
                        new_chat = await chat_repo.create_chat(
                            user_id=user_id, title=new_title
                        )
                        processed_chat_id = new_chat.id
                        chat_title = new_chat.title
                        logger.info(
                            f"Created new chat ID {processed_chat_id} for user {user_id}."
                        )
                        yield self._create_stream_chunk(
                            "chat_info",
                            ChatInfoData(chat_id=processed_chat_id, title=chat_title),
                        )

                    # 2. Save User Message to DB
                    try:
                        await msg_repo.create_message(
                            chat_id=processed_chat_id, role="user", content=message
                        )
                        logger.debug(
                            f"Saved user message to chat ID {processed_chat_id}."
                        )
                    except Exception as db_err:
                        error_message = "Failed to save your message."
                        logger.error(
                            f"DB error saving user message for chat {processed_chat_id}: {db_err}",
                            exc_info=True,
                        )
                        final_status_str = "error"
                        yield self._create_stream_chunk(
                            "error", ErrorData(message=error_message)
                        )
                        return

                    # 3. Format History + Message for Agent
                    history_input_list = await self._format_history_for_agent(
                        history_messages
                    )
                    current_user_message_dict: ChatCompletionMessageParam = {
                        "role": "user",
                        "content": message,
                    }
                    agent_input_list = history_input_list + [current_user_message_dict]
                    logger.debug(
                        f"Prepared agent input list with {len(agent_input_list)} messages."
                    )

                    # 4. Run Agent Stream and Handle Exceptions
                    logger.debug(
                        f"Running agent stream for chat ID {processed_chat_id}"
                    )
                    # Use 'current_tool_call_item: Any' since ToolCallItem isn't directly imported
                    current_tool_call_item: Optional[Any] = None
                    run_succeeded = False

                    try:
                        # The Runner will use the MCP connection managed by the outer 'async with'
                        run_result_stream = Runner.run_streamed(
                            starting_agent=agent,
                            input=agent_input_list,
                        )

                        async for event in run_result_stream.stream_events():
                            logger.debug(
                                f"Stream event for chat {processed_chat_id}: {event.type}"
                            )
                            if event.type == "raw_response_event":
                                # Use isinstance to check the type of event.data safely
                                if (
                                    isinstance(event.data, ResponseTextDeltaEvent)
                                    and event.data.delta
                                ):
                                    delta_text = event.data.delta
                                    agent_response_content += delta_text
                                    yield self._create_stream_chunk(
                                        "text_delta", TextDeltaData(delta=delta_text)
                                    )
                            elif event.type == "run_item_stream_event":
                                item = (
                                    event.item
                                )  # Type here could be ToolCallItem, ToolCallOutputItem etc.
                                if item.type == "tool_call_item":
                                    current_tool_call_item = (
                                        item  # Store the item itself
                                    )
                                    # Access the actual tool call info via raw_item
                                    tool_call_info = item.raw_item
                                    if hasattr(tool_call_info, "name"):
                                        tool_name = tool_call_info.name
                                        tool_input_raw = getattr(
                                            tool_call_info, "arguments", "{}"
                                        )  # Arguments are json string
                                        # Try parsing arguments safely
                                        try:
                                            parsed_input = json.loads(tool_input_raw)
                                        except json.JSONDecodeError:
                                            logger.warning(
                                                f"Could not parse tool input JSON: {tool_input_raw}"
                                            )
                                            parsed_input = {
                                                "raw_arguments": tool_input_raw
                                            }  # Keep raw if not json

                                        # Ensure tool_call_id exists on the item before yielding
                                        tool_call_id = getattr(
                                            item, "tool_call_id", "unknown_call_id"
                                        )

                                        yield self._create_stream_chunk(
                                            "tool_call",
                                            ToolCallData(
                                                id=tool_call_id,
                                                name=tool_name,
                                                input=parsed_input,
                                            ),
                                        )
                                        logger.info(
                                            f"Agent calling tool: {tool_name} in chat {processed_chat_id}"
                                        )
                                    else:
                                        logger.warning(
                                            f"ToolCallItem structure missing name: {item!r}"
                                        )

                                elif item.type == "tool_call_output_item":
                                    tool_output = item.output
                                    output_tool_call_id = getattr(
                                        item, "tool_call_id", None
                                    )

                                    # Handle missing tool_call_id in output item
                                    if not output_tool_call_id:
                                        # First try to get it from the current_tool_call_item if available
                                        if current_tool_call_item:
                                            tool_call_item_id = getattr(
                                                current_tool_call_item,
                                                "tool_call_id",
                                                None,
                                            )
                                            if tool_call_item_id:
                                                # Inject the ID from the current_tool_call_item
                                                item.tool_call_id = tool_call_item_id
                                                output_tool_call_id = tool_call_item_id
                                                logger.info(
                                                    f"Injected tool_call_id {tool_call_item_id} into output item for chat {processed_chat_id}"
                                                )

                                        # If still no ID, generate one to avoid null values
                                        if not output_tool_call_id:
                                            fallback_id = f"auto-{len(tool_calls_data)}-{processed_chat_id}"
                                            item.tool_call_id = fallback_id
                                            output_tool_call_id = fallback_id
                                            logger.info(
                                                f"Generated fallback tool_call_id {fallback_id} for chat {processed_chat_id}"
                                            )

                                    # Store the tool call data for saving to DB later
                                    if current_tool_call_item:
                                        tool_calls_data.append(
                                            (current_tool_call_item, item)
                                        )
                                        current_tool_call_item = (
                                            None  # Reset after pairing
                                        )
                                    else:
                                        logger.warning(
                                            f"Received tool output without matching tool call for chat {processed_chat_id}"
                                        )

                                    # Yield the tool output to the client - always using a valid ID
                                    yield self._create_stream_chunk(
                                        "tool_output",
                                        ToolOutputData(
                                            tool_call_id=output_tool_call_id,
                                            output=tool_output,
                                        ),
                                    )
                                    logger.info(
                                        f"Tool output received for chat {processed_chat_id}"
                                    )
                            elif event.type == "agent_updated_stream_event":
                                logger.info(
                                    f"Agent updated to: {event.new_agent.name} in chat {processed_chat_id}"
                                )

                        # If the loop completes without exceptions, it's successful
                        run_succeeded = True
                        final_status_str = "complete"
                        logger.info(
                            f"Agent stream completed successfully for chat {processed_chat_id}."
                        )

                    # --- Catch specific SDK/Agent exceptions here ---
                    except UserError as ue:
                        error_message = f"Agent UserError: {str(ue)}"
                        logger.error(error_message, exc_info=True)
                        final_status_str = "error"
                        yield self._create_stream_chunk(
                            "error",
                            ErrorData(
                                message="Agent configuration or connection error."
                            ),
                        )
                    except (
                        MaxTurnsExceeded,
                        InputGuardrailTripwireTriggered,
                        OutputGuardrailTripwireTriggered,
                        AgentsException,
                    ) as agent_err:
                        error_message = f"Agent run terminated: {type(agent_err).__name__} - {str(agent_err)}"
                        logger.error(error_message, exc_info=True)
                        final_status_str = "error"
                        yield self._create_stream_chunk(
                            "error", ErrorData(message=error_message)
                        )
                    except (
                        Exception
                    ) as stream_err:  # Catch other errors during streaming
                        error_message = f"Error during agent stream: {str(stream_err)}"
                        logger.error(error_message, exc_info=True)
                        final_status_str = "error"
                        yield self._create_stream_chunk(
                            "error",
                            ErrorData(
                                message="An error occurred during agent processing."
                            ),
                        )
                    # --- End Try/Except around stream ---

                    # 5. Save Agent Response and Tool Usage to DB (only if run succeeded)
                    if run_succeeded and final_status_str == "complete":
                        if agent_response_content:
                            try:
                                assistant_msg = await msg_repo.create_message(
                                    chat_id=processed_chat_id,
                                    role="assistant",
                                    content=agent_response_content.strip(),
                                )
                                logger.debug(
                                    f"Saved assistant message ID {assistant_msg.id} to chat ID {processed_chat_id}."
                                )
                                # Save tool usage linked to the assistant message
                                if tool_calls_data:
                                    for call_item, output_item in tool_calls_data:
                                        # Add extra safety checks here
                                        if (
                                            call_item
                                            and output_item
                                            and hasattr(call_item, "raw_item")
                                            and hasattr(output_item, "output")
                                        ):
                                            tool_call_info = (
                                                call_item.raw_item
                                            )  # Get the raw tool call
                                            tool_input_raw = getattr(
                                                tool_call_info, "arguments", "{}"
                                            )
                                            try:
                                                parsed_input = json.loads(
                                                    tool_input_raw
                                                )
                                            except json.JSONDecodeError:
                                                parsed_input = {
                                                    "raw_arguments": tool_input_raw
                                                }

                                            await msg_repo.create_tool_usage_for_message(
                                                message_id=assistant_msg.id,
                                                tool_name=getattr(
                                                    tool_call_info, "name", "unknown"
                                                ),
                                                tool_input=parsed_input,
                                                tool_output=output_item.output,
                                            )
                                        else:
                                            logger.warning(
                                                f"Skipping saving incomplete tool usage data for msg {assistant_msg.id}: call={call_item!r}, output={output_item!r}"
                                            )
                                    logger.debug(
                                        f"Saved {len(tool_calls_data)} tool usage records for message ID {assistant_msg.id}."
                                    )
                            except Exception as db_err:
                                logger.error(
                                    f"Failed to save assistant response/tools to DB for chat {processed_chat_id}: {db_err}",
                                    exc_info=True,
                                )
                                # Yield error even if DB save fails after successful run
                                yield self._create_stream_chunk(
                                    "error",
                                    ErrorData(
                                        message="Failed to save assistant's response (run was complete)."
                                    ),
                                )
                        else:
                            logger.warning(
                                f"Agent finished run for chat {processed_chat_id} successfully but produced no text content."
                            )
                    elif final_status_str != "error":
                        logger.warning(
                            f"Agent run finished with unexpected status '{final_status_str}' for chat {processed_chat_id}. Assistant response not saved."
                        )
            # --- End 'async with get_async_session()' ---
        # --- End 'async with mcp_server_instance...' ---

        except Exception as outer_err:
            # Catch errors from agent init, DB connection, MCP context entry etc.
            final_status_str = "error"
            error_message = f"Critical error in chat service for user {user_id}, chat {chat_id}: {str(outer_err)}"
            logger.error(error_message, exc_info=True)
            # Yield error chunk if possible
            try:
                yield self._create_stream_chunk(
                    "error", ErrorData(message="An unexpected server error occurred.")
                )
            except Exception:  # Ignore if yield fails during critical error
                pass
        finally:
            # --- No explicit MCP close needed here, 'async with' handles it ---

            # --- Always yield final status ---
            if final_status_str == "unknown" and error_message:
                final_status_str = "error"
            elif final_status_str == "unknown":  # If no error but not marked complete
                final_status_str = "error"  # Assume error if not explicitly completed
                logger.warning(
                    f"Final status was 'unknown' for chat {processed_chat_id}, marking as 'error'."
                )

            logger.info(
                f"Sending final status '{final_status_str}' for chat {processed_chat_id}"
            )
            # Use helper for final status chunk
            yield self._create_stream_chunk(
                "status", StatusData(status=final_status_str, chat_id=processed_chat_id)
            )
            # --- End final status ---
