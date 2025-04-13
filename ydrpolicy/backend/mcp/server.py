# ydrpolicy/backend/mcp/server.py
"""
MCP Server implementation for YDR Policy RAG Tools.

This module sets up a Model Context Protocol (MCP) server using the FastMCP library.
It defines specific tools that can be called by an MCP client (like the Agent).
These tools interact with the application's database to retrieve policy information.
The server can be run using either stdio or http transport.
"""
import logging # Import standard logging
from typing import Any, Dict, List, Optional
import uvicorn # Used for running the server over HTTP

from mcp.server.fastmcp import FastMCP
from rich.logging import RichHandler # Import RichHandler to identify it for removal in stdio mode

from ydrpolicy.backend.config import config
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.repository.policies import PolicyRepository
from ydrpolicy.backend.services.embeddings import embed_text

# Instantiate a logger for this module. Console logging is initially enabled
# but will be disabled later if running in stdio mode.
logger = logging.getLogger(__name__)

# Initialize FastMCP server instance. Tools will be registered using decorators.
# The name "ydrpolicy_mcp" is how this server might be identified by clients.
mcp = FastMCP("ydrpolicy_mcp")


# --- Tool Definitions ---
# Tools are functions exposed via MCP that the agent can call.
# The @mcp.tool() decorator handles registration and schema generation
# based on type hints and docstrings.

@mcp.tool()
async def find_similar_chunks(query: str, k: int, threshold: Optional[float] = None) -> str:
    """
    Finds policy chunks semantically similar to the query using vector embeddings.

    This tool performs a vector similarity search against pre-computed embeddings
    of policy chunks stored in the database.

    Args:
        query: The text query to search for similar policy chunks.
        k: The maximum number of similar chunks to return.
        threshold: Optional minimum similarity score (0-1). If None, uses default
                   from RAG configuration (`config.RAG.SIMILARITY_THRESHOLD`).

    Returns:
        A formatted string listing the top K similar chunks, including their ID,
        similarity score, the ID and title of the policy they belong to, and a snippet
        of their content. Returns an error message on failure or if no sufficiently
        similar chunks are found.
    """
    logger.info(f"Received find_similar_chunks request: query='{query[:50]}...', k={k}, threshold={threshold}")
    sim_threshold = threshold if threshold is not None else config.RAG.SIMILARITY_THRESHOLD

    try:
        logger.debug("Generating embedding for the query...")
        query_embedding = await embed_text(query) # Generate embedding for the input query
        logger.debug(f"Generated embedding with dimension: {len(query_embedding)}")

        # Obtain a database session to interact with the repository
        async with get_async_session() as session:
            policy_repo = PolicyRepository(session)
            logger.debug(f"Searching for chunks with k={k}, threshold={sim_threshold}...")
            # Call the repository method to perform the vector search
            similar_chunks = await policy_repo.search_chunks_by_embedding(
                embedding=query_embedding,
                limit=k,
                similarity_threshold=sim_threshold
            )
            logger.info(f"Found {len(similar_chunks)} similar chunks.")

        # Format the results for the agent
        if not similar_chunks:
            return f"No policy chunks found matching the query with similarity threshold {sim_threshold}."

        output_lines = [f"Found {len(similar_chunks)} similar policy chunks (Top {k} requested):"]
        for i, chunk_info in enumerate(similar_chunks):
            # Extract relevant details from each chunk result dictionary
            chunk_id = chunk_info.get('id', 'N/A')
            similarity_score = chunk_info.get('similarity', 0.0)
            policy_id = chunk_info.get('policy_id', 'N/A')
            policy_title = chunk_info.get('policy_title', 'N/A') # Get policy title
            content_snippet = chunk_info.get('content', '')[:200] + '...' # Limit snippet length

            # Append formatted result to the output list
            output_lines.append(
                f"\n--- Result {i+1} ---\n"
                f"  Chunk ID: {chunk_id}\n"
                f"  Policy ID: {policy_id}\n"
                f"  Policy Title: {policy_title}\n" # Include title
                f"  Similarity: {similarity_score:.4f}\n"
                f"  Content Snippet: {content_snippet}"
            )

        return "\n".join(output_lines) # Return a single formatted string

    except Exception as e:
        logger.error(f"Error in find_similar_chunks: {e}", exc_info=True)
        # Return an informative error message if the tool fails
        return f"An error occurred while searching for similar chunks: {str(e)}"


@mcp.tool()
async def get_policy_from_ID(policy_id: int) -> str:
    """
    Retrieves the full markdown content, title, and source URL of a policy given its ID.

    This tool fetches the complete details of a specific policy document from the
    database based on its unique identifier.

    Args:
        policy_id: The unique identifier (integer) of the policy to retrieve.

    Returns:
        A formatted string containing the policy ID, title, source URL (if available),
        and the full original markdown content. Returns an error message if the
        policy with the given ID is not found.
    """
    logger.info(f"Received get_policy_from_ID request for policy_id: {policy_id}")

    try:
        # Obtain a database session
        async with get_async_session() as session:
            policy_repo = PolicyRepository(session)
            # Fetch the policy object using the repository
            policy = await policy_repo.get_by_id(policy_id)

        # Handle case where policy is not found
        if not policy:
            logger.warning(f"Policy with ID {policy_id} not found.")
            return f"Error: Could not find policy with ID: {policy_id}."

        # Extract details from the retrieved policy object
        retrieved_policy_id = policy.id
        policy_title = policy.title
        policy_url = policy.source_url if policy.source_url else 'N/A' # Handle missing URL
        policy_markdown = policy.markdown_content # Get the full markdown

        # Format the output string
        output = (
            f"Policy Details for ID: {retrieved_policy_id}\n"
            f"----------------------------------------\n"
            f"Title: {policy_title}\n"
            f"Source URL: {policy_url}\n"
            f"----------------------------------------\n"
            f"Policy Markdown Content:\n\n{policy_markdown}"
        )
        return output

    except Exception as e:
        logger.error(f"Error in get_policy_from_ID for policy_id {policy_id}: {e}", exc_info=True)
        # Return an informative error message if the tool fails
        return f"An error occurred while retrieving policy details for Policy ID {policy_id}: {str(e)}"


# --- Server Startup Logic ---

def start_mcp_server(host: str, port: int, transport: str):
    """
    Starts the MCP server using the specified transport mechanism.

    This function handles the setup and execution of the server process.
    It conditionally configures logging based on the transport mode to
    avoid interfering with stdio communication.

    Args:
        host: The hostname or IP address to bind to (for HTTP).
        port: The port number to listen on (for HTTP).
        transport: The transport protocol ('http' or 'stdio').

    Raises:
        ValueError: If an unsupported transport type is provided.
        Exception: Propagates exceptions from the underlying server run methods.
    """
    logger.info(f"Attempting to start MCP server using {transport} transport...")

    # Conditionally disable console logging for stdio mode
    # This prevents log messages from interfering with MCP JSON-RPC communication
    # over stdin/stdout. File logging remains active.
    if transport == 'stdio':
        logger.info("Configuring logger for stdio mode (disabling console propagation)...")
        logger.propagate = False
        logger.info("Disabled log propagation for stdio mode (console logs suppressed).")

    # Start the server based on the chosen transport
    try:
        if transport == 'stdio':
            logger.info("Running MCP server with stdio transport.")
            # The FastMCP library handles stdio communication directly via .run()
            mcp.run(transport=transport)
        elif transport == 'http':
            logger.info(f"Running MCP server with http transport via uvicorn on {host}:{port}.")
            # For HTTP, treat the 'mcp' object as an ASGI application and run it with uvicorn
            uvicorn.run(
                mcp, # The FastMCP instance is the ASGI application
                host=host,
                port=port,
                log_level=config.LOGGING.LEVEL.lower(), # Use log level from config
                # Default workers=1 is usually fine for MCP server
            )
        else:
            # Handle unsupported transport types
            logger.error(f"Unsupported transport type: {transport}")
            raise ValueError(f"Unsupported transport type: {transport}. Choose 'http' or 'stdio'.")

        # This log message might only be reached if the server exits gracefully
        logger.info("MCP server process finished.")
    except Exception as e:
        # Log any exceptions during server execution
        logger.error(f"MCP server run failed: {e}", exc_info=True)
        raise # Re-raise the exception to indicate failure


# --- Main Execution Block ---
# This allows running the MCP server script directly, e.g., using:
# `python -m ydrpolicy.backend.mcp.server` or `uv run ydrpolicy/backend/mcp/server.py`
# It will use the settings defined in `ydrpolicy/backend/config.py`.
if __name__ == "__main__":
    # Retrieve server configuration
    host = config.MCP.HOST
    port = config.MCP.PORT
    transport = config.MCP.TRANSPORT

    logger.info(f"Running MCP server directly ({transport} on {host}:{port})...")
    try:
        # Call the main server startup function
        start_mcp_server(host=host, port=port, transport=transport)
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logger.info("MCP server stopped by user (KeyboardInterrupt).")
    except Exception as e:
        # Errors are logged within start_mcp_server, just exit cleanly
        logger.debug(f"MCP server exited with error: {e}") # Log error at debug level here
        pass

    logger.info("MCP server process stopped.")