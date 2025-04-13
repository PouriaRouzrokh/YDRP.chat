# ydrpolicy/backend/agent/policy_agent.py
"""
Defines the core OpenAI Agent for interacting with Yale Radiology Policies.
"""
import logging
from typing import List, Optional

from agents import Agent, ModelSettings
from agents.mcp import MCPServer

from ydrpolicy.backend.config import config
from ydrpolicy.backend.agent.mcp_connection import get_mcp_server

# Initialize logger
logger = logging.getLogger(__name__)

# Define the system prompt for the agent
SYSTEM_PROMPT = """
You are a specialized AI assistant knowledgeable about the policies and procedures
of the Yale Department of Diagnostic Radiology. Your purpose is to accurately answer
questions based *only* on the official policy documents provided to you through your tools.

Available Tools:
- `find_similar_chunks`: Use this tool first to search for relevant policy sections based on the user's query. Provide the user's query and the desired number of results (e.g., k=5).
- `get_policy_from_ID`: Use this tool *after* `find_similar_chunks` has identified relevant policy IDs. Provide the specific `policy_id` from the search results to retrieve the full text of that policy.

Interaction Flow:
1. When the user asks a question, first use `find_similar_chunks` to locate potentially relevant policy text snippets (chunks).
2. Analyze the results from `find_similar_chunks`. If relevant chunks are found, identify the corresponding `policy_id`(s).
3. If a specific policy seems highly relevant, use `get_policy_from_ID` with the `policy_id` to retrieve the full policy document.
4. Synthesize the information from the retrieved chunks and/or full policies to answer the user's question accurately.
5. ALWAYS cite the Policy ID and Title when providing information extracted from a policy.
6. If the tools do not provide relevant information, state that you cannot find the specific policy information within the available documents and advise the user to consult official departmental resources or personnel.
7. Do not answer questions outside the scope of Yale Diagnostic Radiology policies.
8. Do not invent information or policies. Stick strictly to the content provided by the tools.
"""


async def create_policy_agent(use_mcp: bool = True) -> Agent:
    """
    Factory function to create the Yale Radiology Policy Agent instance.

    Args:
        use_mcp (bool): Whether to configure the agent with MCP tools. Defaults to True.

    Returns:
        Agent: The configured OpenAI Agent instance.
    """
    logger.info(f"Creating Policy Agent (MCP Enabled: {use_mcp})...")

    mcp_servers: List[MCPServer] = []
    if use_mcp:
        try:
            # Get the configured MCP server instance
            # Note: get_mcp_server() returns the configured instance,
            # the Runner manages entering/exiting its context.
            mcp_server_instance = await get_mcp_server()
            mcp_servers.append(mcp_server_instance)
            logger.info("MCP server configured for the agent.")
        except ConnectionError as e:
            logger.error(f"Failed to get MCP server instance: {e}. Agent will run without MCP tools.")
            # Optionally raise the error if MCP is critical
            # raise e
        except Exception as e:
            logger.error(
                f"Unexpected error configuring MCP server: {e}. Agent will run without MCP tools.", exc_info=True
            )

    # Define agent settings
    agent_settings = {
        "name": "YDR Policy Assistant",
        "instructions": SYSTEM_PROMPT,
        "model": config.OPENAI.MODEL,  # Use model from config
        "mcp_servers": mcp_servers if use_mcp else [],
        # No specific 'tools' list needed here if they come *only* from MCP
    }

    # Only add model_settings if the model is not o3-mini, o3-preview, or o1-preview
    if config.OPENAI.MODEL not in ["o3-mini", "o3-preview", "o1-preview"]:
        agent_settings["model_settings"] = (
            ModelSettings(
                temperature=config.OPENAI.TEMPERATURE,
                # max_tokens=config.OPENAI.MAX_TOKENS, # Max tokens usually applies to completion, not the model setting itself directly here
                # tool_choice="auto" # Let the agent decide when to use tools based on instructions
            ),
        )

    # Filter out mcp_servers if not use_mcp
    if not use_mcp:
        del agent_settings["mcp_servers"]
        agent_settings["instructions"] = (
            agent_settings["instructions"].split("Available Tools:")[0] + "\nNote: Tools are currently disabled."
        )

    try:
        policy_agent = Agent(**agent_settings)
        logger.info("SUCCESS: Policy Agent instance created successfully.")
        return policy_agent
    except Exception as e:
        logger.error(f"Failed to create Agent instance: {e}", exc_info=True)
        raise RuntimeError("Could not create the Policy Agent.") from e
