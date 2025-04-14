# ydrpolicy/backend/mcp/server.py
"""
MCP Server implementation for YDR Policy RAG Tools.

Sets up a Model Context Protocol (MCP) server using FastMCP.
Handles both stdio and HTTP (SSE) transport modes.
"""
import logging
from typing import Any, Dict, List, Optional

import uvicorn
# No longer need Starlette or Route directly if using mcp.sse_app()
# from starlette.applications import Starlette
# from starlette.routing import Route

from mcp.server.fastmcp import FastMCP
# No longer need SseServerTransport directly
# from mcp.server.sse import SseServerTransport
from rich.logging import RichHandler

from ydrpolicy.backend.config import config
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.repository.policies import PolicyRepository
from ydrpolicy.backend.services.embeddings import embed_text

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize FastMCP server instance
mcp = FastMCP("ydrpolicy_mcp")


# --- Tool Definitions ---
# (Keep your existing tool definitions @mcp.tool() here - unchanged)
@mcp.tool()
async def find_similar_chunks(query: str, k: int, threshold: Optional[float] = None) -> str:
    """
    Finds policy chunks semantically similar to the query using vector embeddings.

    Args:
        query: The text query to search for similar policy chunks.
        k: The maximum number of similar chunks to return.
        threshold: Optional minimum similarity score (0-1). If None, uses default.

    Returns:
        Formatted string of similar chunks or error message.
    """
    logger.info(f"Received find_similar_chunks request: query='{query[:50]}...', k={k}, threshold={threshold}")
    sim_threshold = threshold if threshold is not None else config.RAG.SIMILARITY_THRESHOLD

    try:
        logger.debug("Generating embedding for the query...")
        query_embedding = await embed_text(query)
        logger.debug(f"Generated embedding with dimension: {len(query_embedding)}")

        async with get_async_session() as session:
            policy_repo = PolicyRepository(session)
            logger.debug(f"Searching for chunks with k={k}, threshold={sim_threshold}...")
            similar_chunks = await policy_repo.search_chunks_by_embedding(
                embedding=query_embedding, limit=k, similarity_threshold=sim_threshold
            )
            logger.info(f"Found {len(similar_chunks)} similar chunks.")

        if not similar_chunks:
            return f"No policy chunks found matching the query with similarity threshold {sim_threshold}."

        output_lines = [f"Found {len(similar_chunks)} similar policy chunks (Top {k} requested):"]
        for i, chunk_info in enumerate(similar_chunks):
            chunk_id = chunk_info.get("id", "N/A")
            similarity_score = chunk_info.get("similarity", 0.0)
            policy_id = chunk_info.get("policy_id", "N/A")
            policy_title = chunk_info.get("policy_title", "N/A")
            content_snippet = chunk_info.get("content", "")[:200] + "..."
            output_lines.append(
                f"\n--- Result {i+1} ---\n"
                f"  Chunk ID: {chunk_id}\n"
                f"  Policy ID: {policy_id}\n"
                f"  Policy Title: {policy_title}\n"
                f"  Similarity: {similarity_score:.4f}\n"
                f"  Content Snippet: {content_snippet}"
            )
        return "\n".join(output_lines)
    except Exception as e:
        logger.error(f"Error in find_similar_chunks: {e}", exc_info=True)
        return f"An error occurred while searching for similar chunks: {str(e)}"


@mcp.tool()
async def get_policy_from_ID(policy_id: int) -> str:
    """
    Retrieves the full markdown content, title, and source URL of a policy given its ID.

    Args:
        policy_id: The unique identifier (integer) of the policy to retrieve.

    Returns:
        Formatted string with policy details or error message.
    """
    logger.info(f"Received get_policy_from_ID request for policy_id: {policy_id}")
    try:
        async with get_async_session() as session:
            policy_repo = PolicyRepository(session)
            policy = await policy_repo.get_by_id(policy_id)
        if not policy:
            logger.warning(f"Policy with ID {policy_id} not found.")
            return f"Error: Could not find policy with ID: {policy_id}."

        retrieved_policy_id = policy.id
        policy_title = policy.title
        policy_url = policy.source_url if policy.source_url else "N/A"
        policy_markdown = policy.markdown_content
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
        return f"An error occurred while retrieving policy details for Policy ID {policy_id}: {str(e)}"


# --- REMOVED ASGI App Setup for HTTP/SSE ---
# We will now use mcp.sse_app() directly

# --- Server Startup Logic ---
def start_mcp_server(host: str, port: int, transport: str):
    """
    Starts the MCP server using the specified transport mechanism.

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
    if transport == "stdio":
        logger.info("Configuring logger for stdio mode (disabling console handler)...")
        root_logger = logging.getLogger()
        rich_handler_found = False
        for h in root_logger.handlers[:]:
            if isinstance(h, RichHandler):
                root_logger.removeHandler(h)
                rich_handler_found = True
                logger.info(f"Removed RichHandler: {h}")
        if rich_handler_found:
            logger.info("Console logging disabled for stdio mode.")
        else:
            logger.warning("Could not find RichHandler to remove for stdio mode.")

    try:
        if transport == "stdio":
            logger.info("Running MCP server with stdio transport.")
            mcp.run(transport=transport) # Stdio is handled by FastMCP directly
        elif transport == "http":
            logger.info(f"Running MCP server with http/sse transport via uvicorn on {host}:{port}.")
            # ******************** CHANGE IS HERE ********************
            # Get the ASGI app specifically designed for SSE from FastMCP
            sse_asgi_app = mcp.sse_app()
            uvicorn.run(
                sse_asgi_app, # Run the app provided by FastMCP
                host=host,
                port=port,
                log_level=config.LOGGING.LEVEL.lower(),
            )
            # ******************************************************
        else:
            logger.error(f"Unsupported transport type: {transport}")
            raise ValueError(f"Unsupported transport type: {transport}. Choose 'http' or 'stdio'.")

        logger.info("MCP server process finished.")
    except Exception as e:
        logger.error(f"MCP server run failed: {e}", exc_info=True)
        raise

# --- Main Execution Block ---
if __name__ == "__main__":
    host = config.MCP.HOST
    port = config.MCP.PORT
    transport = config.MCP.TRANSPORT

    logger.info(f"Running MCP server directly ({transport} on {host}:{port})...")
    try:
        start_mcp_server(host=host, port=port, transport=transport)
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.debug(f"MCP server exited with error: {e}")
        pass

    logger.info("MCP server process stopped.")