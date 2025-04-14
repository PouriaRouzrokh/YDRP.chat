# ydrpolicy/backend/services/chat_service.py
"""
Service layer for handling chat interactions with the Policy Agent,
including database persistence for history using structured input.
Handles errors via exceptions from the agent runner.
"""
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple
import datetime

# Use the correct top-level import
from agents import Runner, Agent, RunResultStreaming, RunResult
from agents.mcp import MCPServerSse # Import specifically for type checking and connect/close

# Import specific exceptions if documented or needed, otherwise use general AgentException
from agents.exceptions import (
    AgentsException,
    MaxTurnsExceeded,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    UserError, # Import UserError to potentially catch it specifically
)
from agents.stream_events import (
    StreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    ToolCallItem,
    ToolCallOutputItem,
)
from openai.types.chat import ChatCompletionMessageParam
from openai.types.responses import ResponseTextDeltaEvent, ToolCall, Function

from ydrpolicy.backend.agent.policy_agent import create_policy_agent
import logging  # Use standard logging

logger = logging.getLogger(__name__)
from ydrpolicy.backend.schemas.chat import (
    StreamChunk,
    StreamChunkData,
    ChatInfoData,
    TextDeltaData,
    ToolCallData,
    ToolOutputData,
    ErrorData,
    StatusData,
)
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.repository.chats import ChatRepository
from ydrpolicy.backend.database.repository.messages import MessageRepository
from ydrpolicy.backend.database.models import Message as DBMessage

# Constants
MAX_HISTORY_MESSAGES = 20


class ChatService:
    """Handles interactions with the Policy Agent, including history persistence."""

    def __init__(self, use_mcp: bool = True):
        self.use_mcp = use_mcp
        self._agent: Optional[Agent] = None
        self._init_task: Optional[asyncio.Task] = None

    async def _initialize_agent(self):
        if self._agent is None:
            logger.info("Initializing Policy Agent for ChatService...")
            try:
                self._agent = await create_policy_agent(use_mcp=self.use_mcp)
                logger.info("Policy Agent initialized successfully in ChatService.")
            except Exception as e:
                logger.error(f"Failed to initialize agent in ChatService: {e}", exc_info=True)
                self._agent = None

    async def get_agent(self) -> Agent:
        if self._agent is None:
            if self._init_task is None or self._init_task.done():
                self._init_task = asyncio.create_task(self._initialize_agent())
            await self._init_task
        if self._agent is None:
            raise RuntimeError("Agent initialization failed. Cannot proceed.")
        return self._agent

    async def _format_history_for_agent(self, history: List[DBMessage]) -> List[ChatCompletionMessageParam]:
        formatted_messages: List[ChatCompletionMessageParam] = []
        limited_history = history[-(MAX_HISTORY_MESSAGES * 2) :]
        for msg in limited_history:
            if msg.role == "user":
                formatted_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # If assistant message has tool calls associated, format them correctly if needed
                # For basic history, just content might be enough, but SDK might expect more
                # Check SDK examples for how tool calls/results are represented in history input
                # For now, keeping it simple:
                formatted_messages.append({"role": "assistant", "content": msg.content})
                # Add tool call representation here if required by the model/SDK for history
        logger.debug(f"Formatted DB history into {len(formatted_messages)} message dicts.")
        return formatted_messages

    async def process_user_message_stream(
        self, user_id: int, message: str, chat_id: Optional[int] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Processes a user message using the agent, handling history and DB persistence.
        Manages MCP connection lifecycle explicitly.
        """
        logger.info(f"Processing message stream for user {user_id}, chat {chat_id}, message: '{message[:100]}...'")
        agent_response_content = ""
        tool_calls_data: List[Tuple[ToolCallItem, Optional[ToolCallOutputItem]]] = []
        final_status_str: str = "unknown"
        error_message: Optional[str] = None
        processed_chat_id: Optional[int] = chat_id
        chat_title: Optional[str] = None
        run_result_stream: Optional[RunResultStreaming] = None
        agent: Optional[Agent] = None # Define agent variable in the scope

        try:
            agent = await self.get_agent() # Get the agent instance

            # --- Explicitly connect MCP if enabled ---
            connected_mcp = False
            if agent.mcp_servers:
                logger.debug("Attempting to connect to MCP server(s)...")
                try:
                    # Assuming only one MCP server for now
                    mcp_server_instance = agent.mcp_servers[0]
                    if isinstance(mcp_server_instance, MCPServerSse):
                       await mcp_server_instance.connect()
                       connected_mcp = True
                       logger.info("MCP server connected successfully.")
                    else:
                       logger.warning("Agent's MCP server is not an expected MCPServerSse instance.")
                except Exception as mcp_conn_err:
                    error_message = f"Failed to connect to MCP server: {mcp_conn_err}"
                    logger.error(error_message, exc_info=True)
                    final_status_str = "error"
                    yield StreamChunk(type="error", data=ErrorData(message="Could not connect to required tools server."))
                    # Clean up agent connection if partially established? Usually handled by close() later
                    return # Stop processing

            # --- Proceed with DB operations and agent run ---
            async with get_async_session() as session:
                chat_repo = ChatRepository(session)
                msg_repo = MessageRepository(session)

                # 1. Ensure Chat Session Exists & Load History
                history_messages: List[DBMessage] = []
                if processed_chat_id:
                    chat = await chat_repo.get_by_user_and_id(chat_id=processed_chat_id, user_id=user_id)
                    if not chat:
                        error_message = f"Chat ID {processed_chat_id} not found or does not belong to user ID {user_id}."
                        logger.error(error_message)
                        final_status_str = "error"
                        yield StreamChunk(type="error", data=ErrorData(message=error_message))
                        return # Stop processing early
                    history_messages = await msg_repo.get_by_chat_id_ordered(
                        chat_id=processed_chat_id, limit=MAX_HISTORY_MESSAGES * 2
                    )
                    chat_title = chat.title
                    logger.debug(f"Loaded {len(history_messages)} messages for chat ID {processed_chat_id}.")
                    yield StreamChunk(type="chat_info", data=ChatInfoData(chat_id=processed_chat_id, title=chat_title))
                else:
                    new_title = message[:80] + ("..." if len(message) > 80 else "")
                    new_chat = await chat_repo.create_chat(user_id=user_id, title=new_title)
                    processed_chat_id = new_chat.id
                    chat_title = new_chat.title
                    logger.info(f"Created new chat ID {processed_chat_id} for user {user_id}.")
                    yield StreamChunk(type="chat_info", data=ChatInfoData(chat_id=processed_chat_id, title=chat_title))

                # 2. Save User Message to DB
                try:
                    await msg_repo.create_message(chat_id=processed_chat_id, role="user", content=message)
                    logger.debug(f"Saved user message to chat ID {processed_chat_id}.")
                except Exception as db_err:
                    error_message = "Failed to save your message."
                    logger.error(f"DB error saving user message for chat {processed_chat_id}: {db_err}", exc_info=True)
                    final_status_str = "error"
                    yield StreamChunk(type="error", data=ErrorData(message=error_message))
                    return

                # 3. Format History + Message for Agent
                history_input_list = await self._format_history_for_agent(history_messages)
                current_user_message_dict: ChatCompletionMessageParam = {"role": "user", "content": message}
                agent_input_list = history_input_list + [current_user_message_dict]
                logger.debug(f"Prepared agent input list with {len(agent_input_list)} messages.")

                # 4. Run Agent Stream and Handle Exceptions
                logger.debug(f"Running agent stream for chat ID {processed_chat_id}")
                current_tool_call_item: Optional[ToolCallItem] = None
                run_succeeded = False

                try:
                    run_result_stream = Runner.run_streamed(
                        starting_agent=agent,
                        input=agent_input_list,
                    )

                    async for event in run_result_stream.stream_events():
                        logger.debug(f"Stream event for chat {processed_chat_id}: {event.type}")
                        if event.type == "raw_response_event":
                            if isinstance(event.data, ResponseTextDeltaEvent) and event.data.delta:
                                agent_response_content += event.data.delta
                                yield StreamChunk(type="text_delta", data=TextDeltaData(delta=event.data.delta))
                        elif event.type == "run_item_stream_event":
                            item = event.item
                            if item.type == "tool_call_item":
                                current_tool_call_item = item
                                tool_call: ToolCall = item.tool_call
                                tool_name = tool_call.function.name
                                tool_input = item.tool_call_input
                                yield StreamChunk(
                                    type="tool_call",
                                    data=ToolCallData(id=item.tool_call_id, name=tool_name, input=tool_input or {}),
                                )
                                logger.info(f"Agent calling tool: {tool_name} in chat {processed_chat_id}")
                            elif item.type == "tool_call_output_item":
                                if current_tool_call_item:
                                    tool_calls_data.append((current_tool_call_item, item))
                                    current_tool_call_item = None # Reset after pairing
                                else:
                                    logger.warning(f"Received tool output without matching tool call for chat {processed_chat_id}")
                                tool_output = item.output
                                yield StreamChunk(
                                    type="tool_output",
                                    data=ToolOutputData(tool_call_id=item.tool_call_id, output=tool_output),
                                )
                                logger.info(f"Tool output received for chat {processed_chat_id}")
                        elif event.type == "agent_updated_stream_event":
                            logger.info(f"Agent updated to: {event.new_agent.name} in chat {processed_chat_id}")

                    # If the loop completes without exceptions from stream_events(), it's successful
                    run_succeeded = True
                    final_status_str = "complete"
                    logger.info(f"Agent stream completed successfully for chat {processed_chat_id}.")

                # Catch specific SDK/Agent errors
                except UserError as ue: # Catch the specific error we saw
                    error_message = f"Agent UserError: {str(ue)}"
                    logger.error(error_message, exc_info=True)
                    final_status_str = "error"
                    yield StreamChunk(type="error", data=ErrorData(message="Agent configuration or connection error."))
                except (
                    MaxTurnsExceeded,
                    InputGuardrailTripwireTriggered,
                    OutputGuardrailTripwireTriggered,
                    AgentsException,
                ) as agent_err:
                    error_message = f"Agent run terminated: {type(agent_err).__name__} - {str(agent_err)}"
                    logger.error(error_message, exc_info=True)
                    final_status_str = "error"
                    yield StreamChunk(type="error", data=ErrorData(message=error_message))
                except Exception as stream_err: # Catch other errors during streaming
                    error_message = f"Error during agent stream: {str(stream_err)}"
                    logger.error(error_message, exc_info=True)
                    final_status_str = "error"
                    yield StreamChunk(
                        type="error", data=ErrorData(message="An error occurred during agent processing.")
                    )

                # 5. Save Agent Response and Tool Usage (only if run succeeded)
                if run_succeeded and final_status_str == "complete":
                    if agent_response_content:
                        try:
                            assistant_msg = await msg_repo.create_message(
                                chat_id=processed_chat_id, role="assistant", content=agent_response_content.strip()
                            )
                            logger.debug(f"Saved assistant message ID {assistant_msg.id} to chat ID {processed_chat_id}.")
                            # Save tool usage linked to the assistant message
                            if tool_calls_data: # Check if there's any tool data
                                for call_item, output_item in tool_calls_data:
                                    if call_item and output_item: # Ensure both parts exist
                                        await msg_repo.create_tool_usage_for_message(
                                            message_id=assistant_msg.id,
                                            tool_name=call_item.tool_call.function.name,
                                            tool_input=call_item.tool_call_input or {},
                                            tool_output=output_item.output,
                                        )
                                    else:
                                         logger.warning(f"Skipping saving incomplete tool usage data for msg {assistant_msg.id}")
                                logger.debug(f"Saved {len(tool_calls_data)} tool usage records for message ID {assistant_msg.id}.")
                        except Exception as db_err:
                            logger.error(
                                f"Failed to save assistant response/tools to DB for chat {processed_chat_id}: {db_err}",
                                exc_info=True,
                            )
                            yield StreamChunk(
                                type="error",
                                data=ErrorData(message="Failed to save assistant's response (run was complete)."),
                            )
                    else:
                        logger.warning(f"Agent finished run for chat {processed_chat_id} successfully but produced no text content.")
                elif final_status_str != "error":
                    logger.warning(
                        f"Agent run finished with unexpected status '{final_status_str}' for chat {processed_chat_id}. Assistant response not saved."
                    )

        except Exception as outer_err:
            final_status_str = "error"
            error_message = f"Critical error in chat service for user {user_id}, chat {chat_id}: {str(outer_err)}"
            logger.error(error_message, exc_info=True)
            try:
                yield StreamChunk(type="error", data=ErrorData(message="An unexpected server error occurred."))
            except Exception:
                pass
        finally:
            # --- Explicitly close MCP connection ---
            if connected_mcp and agent and agent.mcp_servers:
                logger.debug("Attempting to close MCP server connection...")
                try:
                     # Assuming only one MCP server
                     mcp_server_instance = agent.mcp_servers[0]
                     if isinstance(mcp_server_instance, MCPServerSse):
                        await mcp_server_instance.close()
                        logger.info("MCP server connection closed successfully.")
                except Exception as mcp_close_err:
                     logger.error(f"Error closing MCP connection: {mcp_close_err}", exc_info=True)

            # --- Always yield final status ---
            if final_status_str == "unknown" and error_message:
                final_status_str = "error"
            elif final_status_str == "unknown": # If no error but not marked complete
                final_status_str = "error" # Assume error if not explicitly completed
                logger.warning(f"Final status was 'unknown' for chat {processed_chat_id}, marking as 'error'.")


            logger.info(f"Sending final status '{final_status_str}' for chat {processed_chat_id}")
            yield StreamChunk(type="status", data=StatusData(status=final_status_str, chat_id=processed_chat_id))