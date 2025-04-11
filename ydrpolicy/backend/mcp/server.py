# ydrpolicy/backend/mcp/server.py
"""
MCP Server implementation for YDR Policy RAG Tools.

Provides tools for searching policy chunks and retrieving full policies.
"""
# No change to imports needed for this fix
import asyncio # Keep asyncio import for tool functions if they need it directly
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ydrpolicy.backend.config import config
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.repository.policies import PolicyRepository
from ydrpolicy.backend.logger import BackendLogger
from ydrpolicy.backend.services.embeddings import embed_text

# Initialize logger
logger = BackendLogger(name="MCPServer", path=config.LOGGING.FILE)

# Initialize FastMCP server
mcp = FastMCP("ydrpolicy_mcp")

# --- Tool functions (find_similar_chunks, get_policy_from_chunk) ---
# --- remain exactly the same (they are still async) ---

@mcp.tool()
async def find_similar_chunks(query: str, k: int, threshold: Optional[float] = None) -> str:
    # ... (implementation is unchanged) ...
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
                embedding=query_embedding,
                limit=k,
                similarity_threshold=sim_threshold
            )
            logger.info(f"Found {len(similar_chunks)} similar chunks.")
        if not similar_chunks:
            return f"No policy chunks found matching the query with similarity threshold {sim_threshold}."
        output_lines = [f"Found {len(similar_chunks)} similar policy chunks (Top {k} requested):"]
        for chunk_info in similar_chunks:
            chunk_id = chunk_info.get('id', 'N/A')
            similarity_score = chunk_info.get('similarity', 0.0)
            policy_title = chunk_info.get('policy_title', 'Unknown Policy')
            output_lines.append(
                f"  - Chunk ID: {chunk_id}, Similarity: {similarity_score:.4f} (Policy: '{policy_title}')"
            )
        return "\n".join(output_lines)
    except Exception as e:
        logger.error(f"Error in find_similar_chunks: {e}", exc_info=True)
        return f"An error occurred while searching for similar chunks: {str(e)}"

@mcp.tool()
async def get_policy_from_chunk(chunk_id: int) -> str:
    # ... (implementation is unchanged) ...
    logger.info(f"Received get_policy_from_chunk request for chunk_id: {chunk_id}")
    try:
        async with get_async_session() as session:
            policy_repo = PolicyRepository(session)
            policy_details = await policy_repo.get_policy_details_from_chunk_id(chunk_id)
        if not policy_details:
            return f"Error: Could not find policy details for Chunk ID: {chunk_id}."
        policy_id = policy_details.get('policy_id', 'N/A')
        policy_url = policy_details.get('policy_url', 'N/A')
        policy_text = policy_details.get('policy_text', 'Error: Text content missing.')
        output = (
            f"Policy Details for Chunk ID: {chunk_id}\n"
            f"----------------------------------------\n"
            f"Policy ID: {policy_id}\n"
            f"Source URL: {policy_url}\n"
            f"----------------------------------------\n"
            f"Policy Text Content:\n\n{policy_text}"
        )
        return output
    except Exception as e:
        logger.error(f"Error in get_policy_from_chunk for chunk_id {chunk_id}: {e}", exc_info=True)
        return f"An error occurred while retrieving policy details for Chunk ID {chunk_id}: {str(e)}"

# --- CHANGE start_mcp_server TO BE SYNCHRONOUS ---
# Function to run the server (can be called from main.py)
def start_mcp_server(host: str, port: int, transport: str):
    """Starts the MCP server. This is a blocking call."""
    logger.info(f"Attempting to start MCP server on {host}:{port} via {transport} transport...")
    # mcp.run() is blocking and manages its own event loop for async tools.
    try:
        if transport == 'stdio':
            logger.info("Running MCP server with stdio transport.")
            # Call run() ONLY with transport for stdio
            mcp.run(transport=transport)
        elif transport == 'http':
            logger.info(f"Running MCP server with http transport on {host}:{port}.")
            # Call run() WITH host and port for http
            mcp.run(host=host, port=port, transport=transport)
        else:
            logger.error(f"Unsupported transport type: {transport}")
            raise ValueError(f"Unsupported transport type: {transport}")

        # Code here will only execute after the server stops (e.g., Ctrl+C)
        logger.info("MCP server process finished.")
    except Exception as e:
        # Log crash originating from mcp.run or its internals
        logger.error(f"MCP server run failed: {e}", exc_info=True)
        raise # Re-raise exception to signal failure


if __name__ == "__main__":
    # This allows running the server directly using: python -m ydrpolicy.backend.mcp.server
    from ydrpolicy.backend.config import config

    host = config.MCP.HOST
    port = config.MCP.PORT
    transport = config.MCP.TRANSPORT

    logger.info("Running MCP server directly...")
    try:
        # --- CALL DIRECTLY, NO asyncio.run() ---
        start_mcp_server(host=host, port=port, transport=transport)
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user.")
    except Exception as e:
        # Catch exceptions raised by start_mcp_server itself
        logger.error(f"MCP server failed to start or crashed: {e}", exc_info=True)

    logger.info("MCP server stopped.")