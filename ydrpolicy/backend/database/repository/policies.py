# ydrpolicy/backend/database/repository/policies.py
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, func, text, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.sql.expression import or_, and_

from ydrpolicy.backend.database.models import Policy, PolicyChunk, PolicyUpdate, Image
from ydrpolicy.backend.database.repository.base import BaseRepository
from ydrpolicy.backend.config import config
from ydrpolicy.backend.logger import BackendLogger

# Initialize logger
logger = BackendLogger(name=__name__, path=config.LOGGING.FILE)


class PolicyRepository(BaseRepository[Policy]):
    """Repository for working with Policy models and related operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Policy)

    async def get_by_url(self, url: str) -> Optional[Policy]:
        """
        Get a policy by its source URL.

        Args:
            url: Source URL of the policy

        Returns:
            Policy if found, None otherwise
        """
        stmt = select(Policy).where(Policy.source_url == url)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_title(self, title: str) -> Optional[Policy]:
        """
        Get a policy by its exact title (case-sensitive).

        Args:
            title: Exact title of the policy

        Returns:
            Policy if found, None otherwise
        """
        stmt = select(Policy).where(Policy.title == title)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def search_by_title(self, title_query: str, limit: int = 10) -> List[Policy]:
        """
        Search policies by title using case-insensitive partial matching.

        Args:
            title_query: Title search query
            limit: Maximum number of results to return

        Returns:
            List of policies matching the title query
        """
        stmt = (
            select(Policy)
            .where(Policy.title.ilike(f"%{title_query}%"))
            .order_by(desc(Policy.updated_at)) # Order by most recent
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_policy_details(self, policy_id: int) -> Optional[Policy]:
        """
        Get a policy with its chunks and images eagerly loaded.

        Args:
            policy_id: ID of the policy

        Returns:
            Policy object with related data loaded, or None if not found.
        """
        stmt = (
            select(Policy)
            .where(Policy.id == policy_id)
            .options(
                selectinload(Policy.chunks).order_by(PolicyChunk.chunk_index), # Load chunks ordered by index
                selectinload(Policy.images)  # Load images
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def delete_by_id(self, policy_id: int) -> bool:
        """
        Delete a policy and its associated chunks and images by ID.
        Relies on cascade="all, delete-orphan" in the Policy model relationships.

        Args:
            policy_id: ID of the policy to delete

        Returns:
            True if deletion occurred, False if policy not found.
        """
        logger.warning(f"Attempting to delete policy with ID: {policy_id} and all associated data.")
        # First, find the policy to ensure it exists
        policy_to_delete = await self.get_by_id(policy_id)
        if not policy_to_delete:
            logger.error(f"Policy with ID {policy_id} not found for deletion.")
            return False

        try:
            # Delete the policy object. Cascades should handle chunks and images.
            await self.session.delete(policy_to_delete)
            await self.session.flush() # Execute the delete operation
            logger.success(f"Successfully deleted policy ID {policy_id} and associated data.")
            return True
        except Exception as e:
            logger.error(f"Error deleting policy ID {policy_id}: {e}", exc_info=True)
            # Rollback will be handled by the session context manager if used
            return False

    async def delete_by_title(self, title: str) -> bool:
        """
        Delete a policy and its associated chunks and images by its title.

        Args:
            title: Exact title of the policy to delete

        Returns:
            True if deletion occurred, False if policy not found or error occurred.
        """
        policy_to_delete = await self.get_by_title(title)
        if not policy_to_delete:
            logger.error(f"Policy with title '{title}' not found for deletion.")
            return False

        # Call delete_by_id using the found policy's ID
        return await self.delete_by_id(policy_to_delete.id)


    async def full_text_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Perform a full-text search on entire policies (title, description, text_content).

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching policies with relevance scores
        """
        # Convert the query to use '&' for AND logic between terms
        search_query = ' & '.join(query.split())

        stmt = text("""
            SELECT
                p.id,
                p.title,
                p.description,
                p.source_url as url,
                ts_rank(p.search_vector, to_tsquery('english', :query)) AS relevance
            FROM
                policies p
            WHERE
                p.search_vector @@ to_tsquery('english', :query)
            ORDER BY
                relevance DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            stmt,
            {"query": search_query, "limit": limit}
        )

        # Fetch results as mappings (dict-like objects)
        return [dict(row) for row in result.mappings()]


    async def text_search_chunks(self, query: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Perform a text-based search on policy chunks using full-text search.

        Args:
            query: Search query string
            limit: Maximum number of results to return (defaults to config.RAG.TOP_K)

        Returns:
            List of matching chunks with relevance scores
        """
        limit = limit if limit is not None else config.RAG.TOP_K
        logger.info(f"Performing text-only search for query: '{query}' with limit={limit}")

        # Convert the query to use '&' for AND logic
        search_query = ' & '.join(query.split())

        stmt = text("""
            SELECT
                pc.id,
                pc.policy_id,
                pc.chunk_index,
                pc.content,
                p.title as policy_title,
                p.source_url as policy_url,
                ts_rank(pc.search_vector, to_tsquery('english', :query)) AS text_score
            FROM
                policy_chunks pc
            JOIN
                policies p ON pc.policy_id = p.id
            WHERE
                pc.search_vector @@ to_tsquery('english', :query)
            ORDER BY
                text_score DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            stmt,
            {"query": search_query, "limit": limit}
        )

        # Fetch results as mappings
        return [dict(row) for row in result.mappings()]


    async def get_recent_policies(self, limit: int = 10) -> List[Policy]:
        """
        Get most recently added policies.

        Args:
            limit: Maximum number of policies to return

        Returns:
            List of policies ordered by creation date (newest first)
        """
        stmt = select(Policy).order_by(desc(Policy.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


    async def get_recently_updated_policies(self, limit: int = 10) -> List[Policy]:
        """
        Get most recently updated policies.

        Args:
            limit: Maximum number of policies to return

        Returns:
            List of policies ordered by update date (newest first)
        """
        stmt = select(Policy).order_by(desc(Policy.updated_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


    async def create_chunk(self, chunk: PolicyChunk) -> PolicyChunk:
        """
        Create a policy chunk.

        Args:
            chunk: PolicyChunk object to create

        Returns:
            Created PolicyChunk with ID populated
        """
        self.session.add(chunk)
        await self.session.flush()
        await self.session.refresh(chunk)
        return chunk


    async def get_chunks_by_policy_id(self, policy_id: int) -> List[PolicyChunk]:
        """
        Get all chunks for a specific policy, ordered by index.

        Args:
            policy_id: ID of the policy

        Returns:
            List of PolicyChunk objects
        """
        stmt = (
            select(PolicyChunk)
            .where(PolicyChunk.policy_id == policy_id)
            .order_by(PolicyChunk.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


    async def get_chunk_by_id(self, chunk_id: int) -> Optional[PolicyChunk]:
        """
        Get a single chunk by its ID.

        Args:
            chunk_id: ID of the chunk

        Returns:
            PolicyChunk object or None if not found.
        """
        stmt = select(PolicyChunk).where(PolicyChunk.id == chunk_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()


    async def get_chunk_neighbors(self, chunk_id: int, window: int = 1) -> Dict[str, Optional[PolicyChunk]]:
        """
        Get the neighboring chunks (previous and next) for a given chunk ID.

        Args:
            chunk_id: The ID of the target chunk.
            window: The number of neighbors to retrieve on each side (default 1).

        Returns:
            A dictionary containing 'previous' and 'next' lists of PolicyChunk objects.
            Returns {'previous': None, 'next': None} if the target chunk is not found.
        """
        target_chunk = await self.get_chunk_by_id(chunk_id)
        if not target_chunk:
            return {'previous': None, 'next': None}

        policy_id = target_chunk.policy_id
        target_index = target_chunk.chunk_index

        # Query for previous chunks
        prev_stmt = (
            select(PolicyChunk)
            .where(
                PolicyChunk.policy_id == policy_id,
                PolicyChunk.chunk_index >= target_index - window,
                PolicyChunk.chunk_index < target_index
            )
            .order_by(PolicyChunk.chunk_index) # Ascending to get closest first if window > 1
        )
        prev_result = await self.session.execute(prev_stmt)
        previous_chunks = list(prev_result.scalars().all())

        # Query for next chunks
        next_stmt = (
            select(PolicyChunk)
            .where(
                PolicyChunk.policy_id == policy_id,
                PolicyChunk.chunk_index > target_index,
                PolicyChunk.chunk_index <= target_index + window
            )
            .order_by(PolicyChunk.chunk_index) # Ascending to get closest first
        )
        next_result = await self.session.execute(next_stmt)
        next_chunks = list(next_result.scalars().all())

        return {
            'previous': previous_chunks or None, # Return None if list is empty
            'next': next_chunks or None # Return None if list is empty
        }


    async def search_chunks_by_embedding(
        self,
        embedding: List[float],
        limit: int = None,
        similarity_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Find chunks similar to the given embedding using cosine similarity.

        Args:
            embedding: Vector embedding to search for
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of chunks with similarity scores
        """
        limit = limit if limit is not None else config.RAG.TOP_K
        similarity_threshold = similarity_threshold if similarity_threshold is not None else config.RAG.SIMILARITY_THRESHOLD

        logger.info(f"Performing vector-only search with limit={limit}, threshold={similarity_threshold}")

        # <=> is cosine distance. Similarity = 1 - distance.
        stmt = text("""
            SELECT
                pc.id,
                pc.policy_id,
                pc.chunk_index,
                pc.content,
                p.title as policy_title,
                p.source_url as policy_url,
                (1 - (pc.embedding <=> CAST(:embedding AS vector))) AS similarity
            FROM
                policy_chunks pc
            JOIN
                policies p ON pc.policy_id = p.id
            WHERE
                (1 - (pc.embedding <=> CAST(:embedding AS vector))) >= :threshold
            ORDER BY
                similarity DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            stmt,
            {
                "embedding": str(embedding), # Cast list to string for pgvector
                "threshold": similarity_threshold,
                "limit": limit
             }
        )

        # Fetch results as mappings
        return [dict(row) for row in result.mappings()]


    async def hybrid_search(
        self,
        query: str,
        embedding: List[float],
        vector_weight: float = None,
        limit: int = None,
        similarity_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Perform a hybrid search using both vector similarity and text search.

        Args:
            query: Text query for keyword search
            embedding: Vector embedding for similarity search
            vector_weight: Weight for vector search (0-1)
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score threshold (0-1)

        Returns:
            List of chunks with combined scores
        """
        vector_weight = vector_weight if vector_weight is not None else config.RAG.VECTOR_WEIGHT
        limit = limit if limit is not None else config.RAG.TOP_K
        similarity_threshold = similarity_threshold if similarity_threshold is not None else config.RAG.SIMILARITY_THRESHOLD

        logger.info(f"Performing hybrid search with query='{query}', weight={vector_weight}, limit={limit}")

        # Prepare the text search query
        text_query = ' & '.join(query.split())

        # Combine vector and text search with weighted scoring
        # Use CTEs for clarity
        stmt = text("""
            WITH vector_search AS (
                SELECT
                    pc.id,
                    (1 - (pc.embedding <=> CAST(:embedding AS vector))) AS vector_score
                FROM policy_chunks pc
                WHERE (1 - (pc.embedding <=> CAST(:embedding AS vector))) >= :threshold
            ), text_search AS (
                SELECT
                    pc.id,
                    ts_rank(pc.search_vector, to_tsquery('english', :query)) AS text_score
                FROM policy_chunks pc
                WHERE pc.search_vector @@ to_tsquery('english', :query)
            ), combined_results AS (
                SELECT
                    pc.id,
                    pc.policy_id,
                    pc.chunk_index,
                    pc.content,
                    p.title as policy_title,
                    p.source_url as policy_url,
                    COALESCE(vs.vector_score, 0.0) AS vector_score,
                    COALESCE(ts.text_score, 0.0) AS text_score
                FROM policy_chunks pc
                JOIN policies p ON pc.policy_id = p.id
                LEFT JOIN vector_search vs ON pc.id = vs.id
                LEFT JOIN text_search ts ON pc.id = ts.id
                -- Ensure we only include results that match either vector or text search
                WHERE vs.id IS NOT NULL OR ts.id IS NOT NULL
            )
            SELECT
                id,
                policy_id,
                chunk_index,
                content,
                policy_title,
                policy_url,
                vector_score,
                text_score,
                -- Calculate combined score using weighted average
                (:vector_weight * vector_score + (1.0 - :vector_weight) * text_score) AS combined_score
            FROM
                combined_results
            ORDER BY
                combined_score DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            stmt,
            {
                "embedding": str(embedding), # Cast list to string for pgvector
                "query": text_query,
                "threshold": similarity_threshold,
                "vector_weight": vector_weight,
                "limit": limit
            }
        )

        # Fetch results as mappings
        return [dict(row) for row in result.mappings()]


    async def get_policies_from_chunks(self, chunk_results: List[Dict[str, Any]]) -> List[Policy]:
        """
        Retrieve complete policies for chunks returned from a search.

        Args:
            chunk_results: List of chunk results from a search method

        Returns:
            List of complete Policy objects, preserving order of first appearance
            and including associated images.
        """
        # Extract unique policy IDs, preserving order of appearance
        policy_ids_ordered = []
        seen_policy_ids = set()
        for result in chunk_results:
            policy_id = result["policy_id"]
            if policy_id not in seen_policy_ids:
                policy_ids_ordered.append(policy_id)
                seen_policy_ids.add(policy_id)

        if not policy_ids_ordered:
            return []

        logger.info(f"Retrieving {len(policy_ids_ordered)} complete policies from chunk results...")

        # Fetch all policies with images eagerly loaded
        stmt = (
            select(Policy)
            .where(Policy.id.in_(policy_ids_ordered))
            .options(
                selectinload(Policy.images) # Eager load images
            )
        )
        result = await self.session.execute(stmt)
        policies_map = {p.id: p for p in result.scalars().all()}

        # Return policies in the order they appeared in chunk results
        ordered_policies = [policies_map[pid] for pid in policy_ids_ordered if pid in policies_map]
        return ordered_policies


    async def log_policy_update(
        self,
        policy_id: Optional[int], # Make policy_id optional for logging deletion of non-existent item
        admin_id: Optional[int],
        action: str,
        details: Optional[Dict] = None
    ) -> PolicyUpdate:
        """
        Log a policy update operation.

        Args:
            policy_id: ID of the policy being modified (or None if deleting based on title failed)
            admin_id: ID of the admin performing the operation (optional)
            action: Type of action ('create', 'update', 'delete', 'delete_failed')
            details: Additional details about the update (optional)

        Returns:
            Created PolicyUpdate record
        """
        policy_update = PolicyUpdate(
            policy_id=policy_id,
            admin_id=admin_id,
            action=action,
            details=details or {},
            # created_at will use database default
        )

        self.session.add(policy_update)
        await self.session.flush()
        await self.session.refresh(policy_update)

        logger.info(f"Logged policy update: policy_id={policy_id}, action={action}, admin_id={admin_id}")
        return policy_update


    async def get_policy_update_history(self, policy_id: int, limit: int = 50) -> List[PolicyUpdate]:
        """
        Get update history for a specific policy.

        Args:
            policy_id: ID of the policy
            limit: Maximum number of history entries to return

        Returns:
            List of PolicyUpdate records for the policy
        """
        stmt = (
            select(PolicyUpdate)
            .where(PolicyUpdate.policy_id == policy_id)
            .order_by(desc(PolicyUpdate.created_at))
            .limit(limit)
            .options(joinedload(PolicyUpdate.admin)) # Optionally load admin info
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())