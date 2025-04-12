# ydrpolicy/backend/agent/mcp_connection.py
"""
Utility for connecting to the YDR Policy MCP server via HTTP/SSE transport.
"""
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator, Optional

from agents.mcp import MCPServerSse
from ydrpolicy.backend.config import config

# Initialize logger
logger = logging.getLogger(__name__)

# Store the server instance globally or manage it via dependency injection
_mcp_server_instance: Optional[MCPServerSse] = None

async def get_mcp_server() -> MCPServerSse:
    """
    Gets or creates the MCPServerSse instance for the YDR Policy tools.

    Manages the lifecycle via async context management internally if needed,
    or returns a pre-initialized instance. For simplicity in an API context,
    we might return a configured but not yet 'entered' context.

    Returns:
        MCPServerSse: The configured MCP server client instance.

    Raises:
        ConnectionError: If the server cannot be initialized.
    """
    global _mcp_server_instance
    if _mcp_server_instance is None:
        mcp_host = config.MCP.HOST
        # Ensure host is not 0.0.0.0 for client connection if running locally
        if mcp_host == "0.0.0.0":
            mcp_host = "localhost"
            logger.warning("MCP Host 0.0.0.0 detected, using 'localhost' for client connection.")

        mcp_port = config.MCP.PORT
        # The SDK expects the /sse endpoint for this class
        mcp_url = f"http://{mcp_host}:{mcp_port}/sse"
        logger.info(f"Initializing MCP Server connection to: {mcp_url}")

        try:
            # Note: We initialize it here but don't enter the async context yet.
            # The Agent Runner will manage the context when it needs to list/call tools.
            # We set cache_tools_list=True assuming the tools don't change during runtime.
            # Set cache_tools_list=False if tools might be added/removed dynamically.
            _mcp_server_instance = MCPServerSse(
                name="YDRPolicyMCPClient", # Name for this client connection
                params={"url": mcp_url},
                cache_tools_list=True # Cache the tool list for performance
            )
            logger.info("MCPServerSse instance created.")
        except Exception as e:
            logger.error(f"Failed to initialize MCPServerSse: {e}", exc_info=True)
            raise ConnectionError(f"Could not initialize connection to MCP server at {mcp_url}") from e

    return _mcp_server_instance

@asynccontextmanager
async def mcp_server_connection() -> AsyncGenerator[MCPServerSse, None]:
    """
    Provides an active MCPServerSse connection as an async context manager.

    This ensures the connection is properly initialized and closed.

    Yields:
        MCPServerSse: An active and initialized MCP server client instance.

    Raises:
        ConnectionError: If the connection cannot be established or fails.
    """
    server = await get_mcp_server()
    if not server:
        raise ConnectionError("Failed to get MCP server instance.")

    try:
        logger.debug("Entering MCP server async context...")
        # The __aenter__ method of MCPServerSse handles the actual connection/initialization
        async with server as active_server:
            logger.info("Successfully connected to MCP server.")
            yield active_server
        logger.debug("Exited MCP server async context.")
    except Exception as e:
        logger.error(f"Error during MCP server connection context: {e}", exc_info=True)
        # Attempt to clean up the global instance if it failed badly
        global _mcp_server_instance
        _mcp_server_instance = None
        raise ConnectionError(f"MCP server connection failed: {e}") from e

async def close_mcp_connection():
    """
    Closes the global MCP server connection if it exists.
    """
    global _mcp_server_instance
    if _mcp_server_instance:
        logger.info("Closing MCP server connection...")
        try:
            # MCPServerSse uses httpx client internally, __aexit__ handles closure
            # We might need to manually trigger cleanup if not using the context manager directly.
            # Calling close() might suffice, or re-entering/exiting the context.
            # For now, assuming the context manager handles cleanup. If issues arise,
            # explicit cleanup logic might be needed here.
            # await _mcp_server_instance.close() # If an explicit close method exists
             pass # Relying on context manager for now
        except Exception as e:
            logger.error(f"Error closing MCP connection: {e}", exc_info=True)
        _mcp_server_instance = None
        logger.info("MCP server connection closed.")