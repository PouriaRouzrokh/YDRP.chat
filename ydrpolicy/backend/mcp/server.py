# ydrpolicy/backend/mcp/server.py
"""
MCP Server implementation for YDR Policy RAG Tools.

Provides tools for searching policy chunks and retrieving full policies.
"""
import asyncio
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ydrpolicy.backend.config import config
from ydrpolicy.backend.database.engine import get_async_session
from ydrpolicy.backend.database.repository.policies import PolicyRepository
from ydrpolicy.backend.logger import logger
from ydrpolicy.backend.services.embeddings import embed_text

# Initialize FastMCP server
mcp = FastMCP("ydrpolicy_mcp")


@mcp.tool()
async def find_similar_chunks(query: str, k: int, threshold: Optional[float] = None) -> str:
    """
    Finds policy chunks semantically similar to the query.

    Args:
        query: The text query to search for similar policy chunks.
        k: The maximum number of similar chunks to return.
        threshold: Optional minimum similarity score (0-1). If None, uses default from config.

    Returns:
        A formatted string listing the top K similar chunks, including their ID,
        similarity score, the ID of the policy they belong to, and a snippet
        of their content. Returns an error message on failure or if no chunks are found.
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
                embedding=query_embedding,
                limit=k,
                similarity_threshold=sim_threshold
            )
            logger.info(f"Found {len(similar_chunks)} similar chunks.")

        if not similar_chunks:
            return f"No policy chunks found matching the query with similarity threshold {sim_threshold}."

        output_lines = [f"Found {len(similar_chunks)} similar policy chunks (Top {k} requested):"]
        for i, chunk_info in enumerate(similar_chunks):
            chunk_id = chunk_info.get('id', 'N/A')
            similarity_score = chunk_info.get('similarity', 0.0)
            policy_id = chunk_info.get('policy_id', 'N/A') # <-- Get Policy ID
            content_snippet = chunk_info.get('content', '') # <-- Get Content Snippet

            output_lines.append(
                f"\n--- Result {i+1} ---\n"
                f"  Chunk ID: {chunk_id}\n"
                f"  Policy ID: {policy_id}\n" # <-- Added Policy ID
                f"  Similarity: {similarity_score:.4f}\n"
                f"  Content Snippet: {content_snippet}" # <-- Added Content Snippet
            )

        return "\n".join(output_lines)

    except Exception as e:
        logger.error(f"Error in find_similar_chunks: {e}", exc_info=True)
        return f"An error occurred while searching for similar chunks: {str(e)}"

# --- Renamed function and changed parameter ---
@mcp.tool()
async def get_policy_from_ID(policy_id: int) -> str:
    """
    Retrieves the full text content, title, and source URL of a policy given its ID.

    Args:
        policy_id: The unique identifier of the policy to retrieve.

    Returns:
        A formatted string containing the policy ID, title, source URL, and full text content,
        or an error message if the policy is not found.
    """
    logger.info(f"Received get_policy_from_ID request for policy_id: {policy_id}")

    try:
        async with get_async_session() as session:
            policy_repo = PolicyRepository(session)
            # --- Use get_by_id to fetch the policy ---
            policy = await policy_repo.get_by_id(policy_id)

        if not policy:
            # Use the correct input parameter name in the error message
            return f"Error: Could not find policy with ID: {policy_id}."

        # Extract details from the policy object
        retrieved_policy_id = policy.id
        policy_title = policy.title # <-- Get Title
        policy_url = policy.source_url if policy.source_url else 'N/A' # Handle potentially None URL
        policy_markdown = policy.markdown_content

        output = (
            f"Policy Details for ID: {retrieved_policy_id}\n" # Use retrieved ID for confirmation
            f"----------------------------------------\n"
            f"Title: {policy_title}\n" # <-- Added Title
            f"Source URL: {policy_url}\n"
            f"----------------------------------------\n"
            f"Policy Markdown Content:\n\n{policy_markdown}"
        )
        return output

    except Exception as e:
        # Use the correct input parameter name in the error message
        logger.error(f"Error in get_policy_from_ID for policy_id {policy_id}: {e}", exc_info=True)
        return f"An error occurred while retrieving policy details for Policy ID {policy_id}: {str(e)}"

# --- start_mcp_server function remains the same ---
def start_mcp_server(host: str, port: int, transport: str):
    """Starts the MCP server. This is a blocking call."""
    logger.info(f"Attempting to start MCP server on {host}:{port} via {transport} transport...")
    try:
        if transport == 'stdio':
            logger.info("Running MCP server with stdio transport.")
            mcp.run(transport=transport)
        elif transport == 'http':
            logger.info(f"Running MCP server with http transport on {host}:{port}.")
            mcp.run(host=host, port=port, transport=transport)
        else:
            logger.error(f"Unsupported transport type: {transport}")
            raise ValueError(f"Unsupported transport type: {transport}")
        logger.info("MCP server process finished.")
    except Exception as e:
        logger.error(f"MCP server run failed: {e}", exc_info=True)
        raise

# --- __main__ block remains the same ---
if __name__ == "__main__":
    from ydrpolicy.backend.config import config

    host = config.MCP.HOST
    port = config.MCP.PORT
    transport = config.MCP.TRANSPORT

    logger.info("Running MCP server directly...")
    try:
        start_mcp_server(host=host, port=port, transport=transport)
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user.")
    except Exception as e:
        logger.error(f"MCP server failed to start or crashed: {e}", exc_info=True)

    logger.info("MCP server stopped.")