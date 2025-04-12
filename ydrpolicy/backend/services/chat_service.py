# ydrpolicy/backend/services/chat_service.py
"""
Service layer for handling chat interactions with the Policy Agent,
including database persistence for history using structured input.
"""
import asyncio
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple

# Use the correct top-level import
from agents import Runner, Agent, RunResultStreaming, RunResult
from agents.run_context import RunStatus
from agents.stream_events import (
    StreamEvent, RawResponsesStreamEvent, RunItemStreamEvent, ToolCallItem, ToolCallOutputItem
)
# Note: The SDK's internal representation might differ, but the input format
# typically aligns with OpenAI's Chat Completions API message structure.
from openai.types.chat import ChatCompletionMessageParam # Using this type for clarity, though dict works
from openai.types.responses import ResponseTextDeltaEvent, ToolCall, Function

from ydrpolicy.backend.agent.policy_agent import create_policy_agent

# Initialize logger
logger = logging.getLogger(__name__)

from ydrpolicy.backend.schemas.chat import (
    StreamChunk, StreamChunkData, ChatInfoData, TextDeltaData, ToolCallData,
    ToolOutputData, ErrorData, StatusData
)
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.repository.chats import ChatRepository
from ydrpolicy.backend.database.repository.messages import MessageRepository
from ydrpolicy.backend.database.models import Message as DBMessage # Alias

# Constants
# MAX_HISTORY_TOKENS = 3000 # Token counting is more complex with structured input
MAX_HISTORY_MESSAGES = 20 # Limit number of turns (user + assistant pairs) to load/send

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

    async def _format_history_for_agent(
        self,
        history: List[DBMessage]
    ) -> List[ChatCompletionMessageParam]:
        """
        Formats database message history into a list of dictionaries suitable
        for the agent runner's input, mimicking Chat Completions format.

        Args:
            history: List of Message objects from the database.

        Returns:
            A list of message dictionaries.
        """
        formatted_messages: List[ChatCompletionMessageParam] = []
        # Limit history to avoid exceeding context window
        # MAX_HISTORY_MESSAGES defines turns, so limit is *2 for user+assistant
        limited_history = history[-(MAX_HISTORY_MESSAGES * 2):]

        for msg in limited_history:
            if msg.role == "user":
                formatted_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # Add the main assistant text content
                formatted_messages.append({"role": "assistant", "content": msg.content})
                # Represent tool usage *after* the assistant message they belong to.
                # NOTE: The SDK's `to_input_list()` might have a more specific format
                # for representing *completed* tool calls/results in the history.
                # This simplified version just includes the text content.
                # A more complex approach would involve reconstructing tool_call and
                # tool_result message types if the Runner explicitly supports them in input.
                # For now, rely on the text content providing sufficient context.
                # if msg.tool_usages:
                #     for tool_use in msg.tool_usages:
                #         # How to best format this? Maybe add a pseudo message?
                #         # Or rely on the assistant's text mentioning the tool?
                #         pass

        logger.debug(f"Formatted DB history into {len(formatted_messages)} message dicts.")
        return formatted_messages

    async def process_user_message_stream(
        self,
        user_id: int,
        message: str,
        chat_id: Optional[int] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Processes a user message using the agent, handling history and database persistence.
        Uses structured list input for history.
        """
        logger.info(f"Processing message stream for user {user_id}, chat {chat_id}, message: '{message[:100]}...'")
        agent_response_content = ""
        tool_calls_data: List[Tuple[ToolCallItem, Optional[ToolCallOutputItem]]] = []
        final_status: RunStatus = RunStatus.PENDING
        final_error: Optional[str] = None
        processed_chat_id: Optional[int] = chat_id
        chat_title: Optional[str] = None

        try:
            agent = await self.get_agent()

            async with get_async_session() as session:
                chat_repo = ChatRepository(session)
                msg_repo = MessageRepository(session)

                # 1. Ensure Chat Session Exists & Load History
                history_messages: List[DBMessage] = []
                if processed_chat_id:
                    logger.debug(f"Attempting to load existing chat ID: {processed_chat_id}")
                    chat = await chat_repo.get_by_user_and_id(chat_id=processed_chat_id, user_id=user_id)
                    if not chat:
                        error_msg = f"Chat ID {processed_chat_id} not found or does not belong to user ID {user_id}."
                        logger.error(error_msg)
                        yield StreamChunk(type="error", data=ErrorData(message=error_msg))
                        return
                    # Load limited history
                    history_messages = await msg_repo.get_by_chat_id_ordered(chat_id=processed_chat_id, limit=MAX_HISTORY_MESSAGES * 2)
                    chat_title = chat.title
                    logger.debug(f"Loaded {len(history_messages)} messages for chat ID {processed_chat_id}.")
                    yield StreamChunk(
                        type="chat_info",
                        data=ChatInfoData(chat_id=processed_chat_id, title=chat_title)
                    )
                else:
                    logger.info(f"No chat ID provided, creating new chat for user ID {user_id}.")
                    new_title = message[:80] + ('...' if len(message) > 80 else '')
                    new_chat = await chat_repo.create_chat(user_id=user_id, title=new_title)
                    processed_chat_id = new_chat.id
                    chat_title = new_chat.title
                    logger.info(f"Created new chat with ID: {processed_chat_id}")
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
                    return

                # --- UPDATED INPUT PREPARATION ---
                # 3. Format History (as List) + Add Current Message
                history_input_list = await self._format_history_for_agent(history_messages)
                current_user_message_dict: ChatCompletionMessageParam = {"role": "user", "content": message}
                agent_input_list = history_input_list + [current_user_message_dict]
                logger.debug(f"Prepared agent input list with {len(agent_input_list)} messages.")
                # Note: Context window limits for the *list* format are handled by the model/SDK or need explicit token counting.
                # The MAX_HISTORY_MESSAGES provides a basic turn limit.
                # --- END OF UPDATED INPUT PREPARATION ---

                # 4. Run Agent Stream
                logger.debug(f"Running agent stream for chat ID {processed_chat_id}")
                current_tool_call_item: Optional[ToolCallItem] = None

                # Pass the list of message dictionaries as input
                run_result_stream: RunResultStreaming = Runner.run_streamed(
                    starting_agent=agent,
                    input=agent_input_list, # <-- Pass the list here
                )

                async for event in run_result_stream.stream_events():
                    # (Event processing logic remains the same as before)
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
                            current_tool_call_item = item
                            tool_call: ToolCall = item.tool_call
                            tool_name = tool_call.function.name
                            tool_input = item.tool_call_input
                            yield StreamChunk(type="tool_call", data=ToolCallData(id=item.tool_call_id, name=tool_name, input=tool_input or {}))
                            logger.info(f"Agent calling tool: {tool_name} in chat {processed_chat_id}")
                        elif item.type == "tool_call_output_item":
                             if current_tool_call_item:
                                 tool_calls_data.append((current_tool_call_item, item))
                                 current_tool_call_item = None
                             tool_output = item.output
                             yield StreamChunk(type="tool_output", data=ToolOutputData(tool_call_id=item.tool_call_id, output=tool_output))
                             logger.info(f"Tool returned output for chat {processed_chat_id}: {str(tool_output)[:100]}...")
                    elif event.type == "agent_updated_stream_event":
                        logger.info(f"Agent updated to: {event.new_agent.name} in chat {processed_chat_id}")
                    elif event.type == "run_complete_event":
                        run_result: RunResult = event.result
                        final_status = run_result.status
                        if run_result.error:
                            final_error = str(run_result.error)
                        logger.info(f"Agent run completed for chat {processed_chat_id} with status: {final_status}")
                        break

                # 5. Save Agent Response and Tool Usage to DB (logic remains the same)
                if final_status == RunStatus.COMPLETE or final_status == RunStatus.REQUIRES_HANDOFF:
                    if agent_response_content:
                        try:
                            assistant_msg = await msg_repo.create_message(
                                chat_id=processed_chat_id,
                                role="assistant",
                                content=agent_response_content.strip()
                            )
                            logger.debug(f"Saved assistant message ID {assistant_msg.id} to chat ID {processed_chat_id}.")

                            for call_item, output_item in tool_calls_data:
                                if not output_item: continue
                                await msg_repo.create_tool_usage_for_message(
                                    message_id=assistant_msg.id,
                                    tool_name=call_item.tool_call.function.name,
                                    tool_input=call_item.tool_call_input or {},
                                    tool_output=output_item.output,
                                )
                            logger.debug(f"Saved {len(tool_calls_data)} tool usage records for message ID {assistant_msg.id}.")

                        except Exception as db_err:
                            logger.error(f"Failed to save assistant response/tools to DB for chat {processed_chat_id}: {db_err}", exc_info=True)
                            yield StreamChunk(type="error", data=ErrorData(message="Failed to save assistant's response."))
                    else:
                         logger.warning(f"Agent finished run for chat {processed_chat_id} but produced no text content.")
                else:
                    error_msg = f"Agent run failed for chat {processed_chat_id}: {final_error or 'Unknown error'}"
                    logger.error(error_msg)
                    yield StreamChunk(type="error", data=ErrorData(message=f"Agent processing failed: {final_error or 'Unknown error'}"))

                yield StreamChunk(type="status", data=StatusData(status=final_status.value, chat_id=processed_chat_id))


        except Exception as e:
            final_status = RunStatus.ERROR
            error_msg = f"Critical error in chat service for user {user_id}, chat {chat_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield StreamChunk(type="error", data=ErrorData(message="An unexpected error occurred."))
            yield StreamChunk(type="status", data=StatusData(status=final_status.value, chat_id=processed_chat_id))