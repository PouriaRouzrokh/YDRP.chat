# ydrpolicy/backend/services/chat_service.py
"""
Service layer for handling chat interactions with the Policy Agent,
including database persistence for history.
"""
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple
import datetime

from agents import Runner, Agent
from agents.run_context import RunStatus
from agents import RunResultStreaming, RunResult
from agents.stream_events import StreamEvent, RawResponsesStreamEvent, RunItemStreamEvent, ToolCallItem, ToolCallOutputItem
from openai.types.responses import ResponseTextDeltaEvent, ToolCall, Function

from ydrpolicy.backend.agent.policy_agent import create_policy_agent
from ydrpolicy.backend.logger import logger
from ydrpolicy.backend.schemas.chat import StreamChunk, StreamChunkData, ChatInfoData, TextDeltaData, ToolCallData, ToolOutputData, ErrorData, StatusData
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.repository.chats import ChatRepository
from ydrpolicy.backend.database.repository.messages import MessageRepository
from ydrpolicy.backend.database.models import Message as DBMessage # Alias to avoid confusion

# Constants
MAX_HISTORY_TOKENS = 3000 # Simple approximation for context window management
MAX_HISTORY_MESSAGES = 20 # Limit number of turns to load/send

class ChatService:
    """Handles interactions with the Policy Agent, including history persistence."""

    def __init__(self, use_mcp: bool = True):
        """
        Initializes the ChatService.

        Args:
            use_mcp (bool): Whether the agent should use MCP tools.
        """
        self.use_mcp = use_mcp
        self._agent: Optional[Agent] = None
        self._init_task: Optional[asyncio.Task] = None
        # We'll get repositories within the processing method using the session context

    async def _initialize_agent(self):
        """Initializes the agent instance asynchronously."""
        if self._agent is None:
            logger.info("Initializing Policy Agent for ChatService...")
            try:
                self._agent = await create_policy_agent(use_mcp=self.use_mcp)
                logger.info("Policy Agent initialized successfully in ChatService.")
            except Exception as e:
                logger.error(f"Failed to initialize agent in ChatService: {e}", exc_info=True)
                self._agent = None

    async def get_agent(self) -> Agent:
        """Gets the initialized agent instance."""
        if self._agent is None:
            if self._init_task is None or self._init_task.done():
                self._init_task = asyncio.create_task(self._initialize_agent())
            await self._init_task

        if self._agent is None:
            raise RuntimeError("Agent initialization failed. Cannot proceed.")
        return self._agent

    async def _format_history_for_agent(self, history: List[DBMessage]) -> str:
        """
        Formats database message history into a single string suitable for agent input.
        Applies simple truncation based on message count.

        Args:
            history: List of Message objects from the database.

        Returns:
            A formatted string representing the conversation history.
        """
        formatted_lines = []
        # Limit history to avoid exceeding context window
        limited_history = history[-MAX_HISTORY_MESSAGES:] # Take the last N messages

        for msg in limited_history:
            role_display = "User" if msg.role == "user" else "Assistant"
            formatted_lines.append(f"{role_display}: {msg.content}")
            # Include tool usage information for assistant messages if available
            if msg.role == 'assistant' and msg.tool_usages:
                 for tool_use in msg.tool_usages:
                      formatted_lines.append(f"[Tool Used: {tool_use.tool_name}]")
                      # Optionally include input/output if needed for context, but can be verbose
                      # formatted_lines.append(f"[Tool Input: {tool_use.input}]")
                      # formatted_lines.append(f"[Tool Output: {tool_use.output}]")

        return "\n".join(formatted_lines)


    async def process_user_message_stream(
        self,
        user_id: int,
        message: str,
        chat_id: Optional[int] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Processes a user message using the agent, handling history and database persistence.

        Args:
            user_id: The ID of the user making the request.
            message: The user's current message.
            chat_id: The optional ID of the chat session to continue or create.

        Yields:
            StreamChunk: Chunks of the response as they become available.
        """
        logger.info(f"Processing message stream for user {user_id}, chat {chat_id}, message: '{message[:100]}...'")
        agent_response_content = ""
        tool_calls_data: List[Tuple[ToolCallItem, Optional[ToolCallOutputItem]]] = []
        final_status: RunStatus = RunStatus.PENDING
        final_error: Optional[str] = None
        processed_chat_id: Optional[int] = chat_id # Will hold the ID of the chat (new or existing)

        try:
            agent = await self.get_agent()

            async with get_async_session() as session:
                chat_repo = ChatRepository(session)
                msg_repo = MessageRepository(session)

                # 1. Ensure Chat Session Exists & Load History
                history: List[DBMessage] = []
                chat_title: Optional[str] = None
                if processed_chat_id:
                    logger.debug(f"Attempting to load existing chat ID: {processed_chat_id}")
                    chat = await chat_repo.get_by_user_and_id(chat_id=processed_chat_id, user_id=user_id)
                    if not chat:
                        error_msg = f"Chat ID {processed_chat_id} not found or does not belong to user ID {user_id}."
                        logger.error(error_msg)
                        yield StreamChunk(type="error", data=ErrorData(message=error_msg))
                        return # Stop processing
                    history = await msg_repo.get_by_chat_id_ordered(chat_id=processed_chat_id, limit=MAX_HISTORY_MESSAGES)
                    chat_title = chat.title
                    logger.debug(f"Loaded {len(history)} messages for chat ID {processed_chat_id}.")
                else:
                    logger.info(f"No chat ID provided, creating new chat for user ID {user_id}.")
                    # Create a simple title from the first message
                    new_title = message[:80] + ('...' if len(message) > 80 else '')
                    new_chat = await chat_repo.create_chat(user_id=user_id, title=new_title)
                    processed_chat_id = new_chat.id
                    chat_title = new_chat.title
                    logger.info(f"Created new chat with ID: {processed_chat_id}")
                    # Yield info about the newly created chat
                    yield StreamChunk(
                        type="chat_info",
                        data=ChatInfoData(chat_id=processed_chat_id, title=chat_title)
                    )

                # 2. Save User Message to DB
                try:
                    await msg_repo.create_message(chat_id=processed_chat_id, role="user", content=message)
                    logger.debug(f"Saved user message to chat ID {processed_chat_id}.")
                except Exception as db_err:
                    logger.error(f"Failed to save user message to DB for chat {processed_chat_id}: {db_err}", exc_info=True)
                    yield StreamChunk(type="error", data=ErrorData(message="Failed to save your message."))
                    # Optionally stop here, or try to continue the agent call anyway
                    return

                # 3. Format History + Message for Agent
                formatted_history = await self._format_history_for_agent(history)
                agent_input = f"{formatted_history}\n\nUser: {message}".strip()
                # TODO: Add more sophisticated token counting/truncation if needed
                if len(agent_input) > MAX_HISTORY_TOKENS * 4: # Rough character approximation
                    logger.warning(f"Agent input length ({len(agent_input)}) might be too long, truncating.")
                    agent_input = agent_input[-MAX_HISTORY_TOKENS*4:]

                # 4. Run Agent Stream
                logger.debug(f"Running agent stream for chat ID {processed_chat_id}")
                current_tool_call_item: Optional[ToolCallItem] = None

                run_result_stream: RunResultStreaming = Runner.run_streamed(
                    starting_agent=agent,
                    input=agent_input,
                )

                async for event in run_result_stream.stream_events():
                    logger.debug(f"Stream event for chat {processed_chat_id}: {event.type}")
                    if event.type == "raw_response_event":
                        if isinstance(event.data, ResponseTextDeltaEvent):
                            text_delta = event.data.delta
                            if text_delta:
                                agent_response_content += text_delta
                                yield StreamChunk(type="text_delta", data=TextDeltaData(delta=text_delta))
                    elif event.type == "run_item_stream_event":
                        item = event.item
                        if item.type == "tool_call_item":
                            current_tool_call_item = item # Store the call item
                            tool_call: ToolCall = item.tool_call
                            tool_name = tool_call.function.name
                            tool_input = item.tool_call_input # Use the parsed input from the item
                            yield StreamChunk(type="tool_call", data=ToolCallData(id=item.tool_call_id, name=tool_name, input=tool_input or {}))
                            logger.info(f"Agent calling tool: {tool_name} in chat {processed_chat_id}")
                        elif item.type == "tool_call_output_item":
                             if current_tool_call_item:
                                 tool_calls_data.append((current_tool_call_item, item))
                                 current_tool_call_item = None # Reset after pairing
                             tool_output = item.output # Use the output from the item
                             yield StreamChunk(type="tool_output", data=ToolOutputData(tool_call_id=item.tool_call_id, output=tool_output))
                             logger.info(f"Tool returned output for chat {processed_chat_id}: {str(tool_output)[:100]}...")
                         # Handle other item types if needed
                    elif event.type == "agent_updated_stream_event":
                        logger.info(f"Agent updated to: {event.new_agent.name} in chat {processed_chat_id}")
                    elif event.type == "run_complete_event":
                        run_result: RunResult = event.result
                        final_status = run_result.status
                        if run_result.error:
                            final_error = str(run_result.error)
                        logger.info(f"Agent run completed for chat {processed_chat_id} with status: {final_status}")
                        break # Exit the loop once run is complete

                # 5. Save Agent Response and Tool Usage to DB (after stream ends)
                if final_status == RunStatus.COMPLETE or final_status == RunStatus.REQUIRES_HANDOFF: # Consider requires_handoff a success for saving
                    if agent_response_content:
                        try:
                            assistant_msg = await msg_repo.create_message(
                                chat_id=processed_chat_id,
                                role="assistant",
                                content=agent_response_content.strip()
                            )
                            logger.debug(f"Saved assistant message ID {assistant_msg.id} to chat ID {processed_chat_id}.")

                            # Save tool usage linked to the assistant message
                            for call_item, output_item in tool_calls_data:
                                if not output_item: continue # Should not happen if paired correctly
                                await msg_repo.create_tool_usage_for_message(
                                    message_id=assistant_msg.id,
                                    tool_name=call_item.tool_call.function.name,
                                    tool_input=call_item.tool_call_input or {},
                                    tool_output=output_item.output,
                                    # execution_time = ? # SDK might provide this in future
                                )
                            logger.debug(f"Saved {len(tool_calls_data)} tool usage records for message ID {assistant_msg.id}.")

                        except Exception as db_err:
                            logger.error(f"Failed to save assistant response/tools to DB for chat {processed_chat_id}: {db_err}", exc_info=True)
                            # Yield an error, but the conversation happened, just wasn't saved fully
                            yield StreamChunk(type="error", data=ErrorData(message="Failed to save assistant's response."))
                    else:
                         logger.warning(f"Agent finished run for chat {processed_chat_id} but produced no text content.")
                else:
                    # Handle error status, log the error captured in final_error
                    error_msg = f"Agent run failed for chat {processed_chat_id}: {final_error or 'Unknown error'}"
                    logger.error(error_msg)
                    yield StreamChunk(type="error", data=ErrorData(message=f"Agent processing failed: {final_error or 'Unknown error'}"))

                # Yield final status update including the chat_id
                yield StreamChunk(type="status", data=StatusData(status=final_status.value, chat_id=processed_chat_id))


        except Exception as e:
            final_status = RunStatus.ERROR
            error_msg = f"Critical error in chat service for user {user_id}, chat {chat_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield StreamChunk(type="error", data=ErrorData(message="An unexpected error occurred."))
            # Yield final status update even on critical failure
            yield StreamChunk(type="status", data=StatusData(status=final_status.value, chat_id=processed_chat_id))