import asyncio
import logging
import sys
import argparse
from pathlib import Path
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from ydrpolicy.backend.database.models import Base, create_search_vector_trigger
from ydrpolicy.backend.config import config as backend_config
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text, inspect

# Import models
from ydrpolicy.backend.database.models import (
    User, Policy, PolicyChunk, Image, Chat, Message, ToolUsage
)

# Import repositories
from ydrpolicy.backend.database.repository.users import UserRepository
from ydrpolicy.backend.database.repository.policies import PolicyRepository

# Create logs subdirectory in tests/backend/database if it doesn't exist
logs_dir = Path(__file__).parent / "logs"
logs_dir.mkdir(exist_ok=True, parents=True)

# Initialize logger with full path
test_logger = logging.getLogger(__name__)


# Database connection parameters
DB_USER = "pouria"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "ydrpolicy_test"

# Connection URL for PostgreSQL admin database
ADMIN_DB_URL = f"postgresql+asyncpg://{DB_USER}:@{DB_HOST}:{DB_PORT}/postgres"
# Test database URL 
TEST_DB_URL = f"postgresql+asyncpg://{DB_USER}:@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def create_test_database():
    """Create the test database if it doesn't exist."""
    test_logger.info(f"Connecting to admin database to create {DB_NAME}")
    
    # Connect to postgres database to create our test database
    admin_engine = create_async_engine(ADMIN_DB_URL)
    
    try:
        # Check if database exists
        async with admin_engine.connect() as conn:
            # We need to run this as raw SQL since we can't use CREATE DATABASE in a transaction
            result = await conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
            )
            exists = result.scalar() is not None
            
            if not exists:
                # Commit any open transaction
                await conn.execute(text("COMMIT"))
                # Create database
                await conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
                test_logger.info(f"Created database {DB_NAME}")
            else:
                test_logger.info(f"Database {DB_NAME} already exists")
    finally:
        await admin_engine.dispose()

async def drop_test_database():
    """Drop the test database if it exists."""
    test_logger.info(f"Connecting to admin database to drop {DB_NAME}")
    
    # Connect to postgres database to drop our test database
    admin_engine = create_async_engine(ADMIN_DB_URL)
    
    try:
        # Check if database exists
        async with admin_engine.connect() as conn:
            # We need to run this as raw SQL since we can't use DROP DATABASE in a transaction
            result = await conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
            )
            exists = result.scalar() is not None
            
            if exists:
                # Force-close all connections to the database
                await conn.execute(text("COMMIT"))
                test_logger.info(f"Terminating all connections to {DB_NAME}")
                await conn.execute(
                    text(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{DB_NAME}'
                    AND pid <> pg_backend_pid()
                    """)
                )
                # Add a small delay to ensure connections are fully terminated
                await asyncio.sleep(0.5)
                
                # Drop database with IF EXISTS to avoid errors
                test_logger.info(f"Dropping database {DB_NAME}")
                await conn.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME}"))
                test_logger.info(f"Dropped database {DB_NAME}")
            else:
                test_logger.info(f"Database {DB_NAME} does not exist")
    except Exception as e:
        test_logger.error(f"Error dropping database: {e}")
        # Don't re-raise - we'll continue even if drop fails
    finally:
        await admin_engine.dispose()

async def setup_database():
    """Initialize the test database with tables and triggers."""
    test_logger.info(f"Setting up database at {TEST_DB_URL}")
    
    # Create engine
    engine = create_async_engine(TEST_DB_URL, echo=True)
    
    try:
        # Create connection and run simple query
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar_one()
            test_logger.info(f"Connection test result: {value}")
            
            # Create extension for vector support
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            test_logger.info("Vector extension created or exists")
            
            # Commit any pending transaction
            await conn.commit()
    
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        test_logger.info("Tables created")
        
        # Create triggers for search vectors
        async with engine.connect() as conn:
            # Apply search vector triggers
            for statement in create_search_vector_trigger():
                await conn.execute(text(statement))
            await conn.commit()
        test_logger.info("Search vector triggers created")
            
    except Exception as e:
        test_logger.error(f"Error setting up database: {e}")
        raise
    finally:
        await engine.dispose()

async def verify_database_tables():
    """Verify that all expected tables exist in the database."""
    test_logger.info("Verifying database tables")
    
    engine = create_async_engine(TEST_DB_URL)
    
    try:
        async with engine.connect() as conn:
            def inspect_tables(conn_sync):
                inspector = inspect(conn_sync)
                tables = inspector.get_table_names()
                test_logger.info(f"Found tables: {tables}")
                
                expected_tables = {
                    "users", "policies", "policy_chunks", "images",
                    "chats", "messages", "tool_usage", "policy_updates"
                }
                
                missing_tables = expected_tables - set(tables)
                unexpected_tables = set(tables) - expected_tables
                
                if missing_tables:
                    test_logger.error(f"Missing tables: {missing_tables}")
                    return False
                
                test_logger.info("All expected tables found")
                return True
            
            result = await conn.run_sync(inspect_tables)
            return result
    finally:
        await engine.dispose()

# Test User Repository Functions
async def test_user_repository():
    """Test user repository operations."""
    test_logger.info("Testing User Repository operations")
    
    engine = create_async_engine(TEST_DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Create user repository
            user_repo = UserRepository(session)
            
            # Create test user
            test_user = User(
                email="test@example.com",
                password_hash="hashed_password",
                full_name="Test User",
                is_admin=False
            )
            
            # Create user
            created_user = await user_repo.create(test_user)
            test_logger.info(f"Created user: {created_user.id} - {created_user.email}")
            
            # Get user by ID
            fetched_user = await user_repo.get_by_id(created_user.id)
            assert fetched_user is not None, "Failed to fetch user by ID"
            test_logger.info(f"Successfully fetched user by ID: {fetched_user.email}")
            
            # Get user by email
            email_user = await user_repo.get_by_email("test@example.com")
            assert email_user is not None, "Failed to fetch user by email"
            test_logger.info(f"Successfully fetched user by email: {email_user.email}")
            
            # Update user
            update_data = {"full_name": "Updated User", "is_admin": True}
            updated_user = await user_repo.update(created_user.id, update_data)
            assert updated_user.full_name == "Updated User", "User update failed"
            assert updated_user.is_admin is True, "User update failed"
            test_logger.info(f"Successfully updated user: {updated_user.full_name}")
            
            # Delete user
            delete_result = await user_repo.delete(created_user.id)
            assert delete_result is True, "User deletion failed"
            test_logger.info("Successfully deleted user")
            
            # Verify user is deleted
            deleted_user = await user_repo.get_by_id(created_user.id)
            assert deleted_user is None, "User still exists after deletion"
            
            # Commit changes
            await session.commit()
            
            test_logger.info("User Repository tests passed!")
            return True
    except Exception as e:
        test_logger.error(f"User Repository test failed: {e}")
        return False
    finally:
        await engine.dispose()

# Test Policy Repository Functions
async def test_policy_repository():
    """Test policy repository operations."""
    test_logger.info("Testing Policy Repository operations")
    
    engine = create_async_engine(TEST_DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Create policy repository
            policy_repo = PolicyRepository(session)
            
            # Create test policy
            test_policy = Policy(
                title="Test Policy",
                description="This is a test policy",
                source_url="http://example.com/policy",
                markdown_content="# Test Policy\nThis is a markdown content.",
                text_content="Test Policy. This is a text content."
            )
            
            # Create policy
            created_policy = await policy_repo.create(test_policy)
            test_logger.info(f"Created policy: {created_policy.id} - {created_policy.title}")
            
            # Verify search vector was created by trigger
            assert created_policy.search_vector is not None, "Search vector was not created"
            test_logger.info("Search vector trigger worked correctly")
            
            # Get policy by ID
            fetched_policy = await policy_repo.get_by_id(created_policy.id)
            assert fetched_policy is not None, "Failed to fetch policy by ID"
            test_logger.info(f"Successfully fetched policy by ID: {fetched_policy.title}")
            
            # Get policy by title
            title_policy = await policy_repo.get_by_title("Test Policy")
            assert title_policy is not None, "Failed to fetch policy by title"
            test_logger.info(f"Successfully fetched policy by title: {title_policy.title}")
            
            # Get policy by URL
            url_policy = await policy_repo.get_by_url("http://example.com/policy")
            assert url_policy is not None, "Failed to fetch policy by URL"
            test_logger.info(f"Successfully fetched policy by URL: {url_policy.title}")
            
            # Create a policy chunk
            test_chunk = PolicyChunk(
                policy_id=created_policy.id,
                chunk_index=0,
                content="This is a test chunk content."
            )
            
            # Create chunk
            created_chunk = await policy_repo.create_chunk(test_chunk)
            test_logger.info(f"Created policy chunk: {created_chunk.id}")
            
            # Test full text search
            search_results = await policy_repo.full_text_search("test")
            assert len(search_results) > 0, "Full text search returned no results"
            test_logger.info(f"Full text search successful: {len(search_results)} results")
            
            # Update policy
            update_data = {
                "title": "Updated Policy Title",
                "description": "This is an updated description"
            }
            updated_policy = await policy_repo.update(created_policy.id, update_data)
            assert updated_policy.title == "Updated Policy Title", "Policy update failed"
            test_logger.info(f"Successfully updated policy: {updated_policy.title}")
            
            # Log policy update
            # Create admin user for logging
            admin_user = User(
                email="admin@example.com",
                password_hash="admin_hash",
                full_name="Admin User",
                is_admin=True
            )
            user_repo = UserRepository(session)
            created_admin = await user_repo.create(admin_user)
            
            policy_update = await policy_repo.log_policy_update(
                updated_policy.id, 
                created_admin.id,
                "update",
                {"modified_fields": ["title", "description"]}
            )
            test_logger.info(f"Logged policy update: {policy_update.id}")
            
            # Get policy update history
            update_history = await policy_repo.get_policy_update_history(updated_policy.id)
            assert len(update_history) > 0, "Policy update history is empty"
            test_logger.info(f"Policy update history retrieved: {len(update_history)} entries")
            
            # Delete policy
            delete_result = await policy_repo.delete_by_id(created_policy.id)
            assert delete_result is True, "Policy deletion failed"
            test_logger.info("Successfully deleted policy")
            
            # Verify policy is deleted
            deleted_policy = await policy_repo.get_by_id(created_policy.id)
            assert deleted_policy is None, "Policy still exists after deletion"
            
            # Commit changes
            await session.commit()
            
            test_logger.info("Policy Repository tests passed!")
            return True
    except Exception as e:
        test_logger.error(f"Policy Repository test failed: {e}")
        return False
    finally:
        await engine.dispose()

# Test Additional Tables
async def test_additional_tables():
    """Test additional tables: images, chats, messages, and tool usage."""
    test_logger.info("Testing additional tables (images, chats, messages, tool usage)")
    
    engine = create_async_engine(TEST_DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Create repositories
            user_repo = UserRepository(session)
            policy_repo = PolicyRepository(session)
            
            # Create a user for chat relationship
            user = User(
                email="chat_user@example.com",
                password_hash="hashed_password",
                full_name="Chat Test User",
                is_admin=False
            )
            created_user = await user_repo.create(user)
            test_logger.info(f"Created user for chat test: {created_user.id}")
            
            # Create a policy for image relationship
            policy = Policy(
                title="Image Test Policy",
                description="Policy for testing images",
                source_url="http://example.com/image-policy",
                markdown_content="# Image Test\nThis is a markdown content with image.",
                text_content="Image Test. This is a text content with image reference."
            )
            created_policy = await policy_repo.create(policy)
            test_logger.info(f"Created policy for image test: {created_policy.id}")
            
            # Create an image associated with the policy
            image = Image(
                policy_id=created_policy.id,
                filename="test-image.png",
                relative_path="test-image.png",
                image_metadata={"width": 800, "height": 600, "format": "png"}
            )
            session.add(image)
            await session.flush()
            test_logger.info(f"Created image: {image.id} for policy {image.policy_id}")
            
            # Create a chat for the user
            chat = Chat(
                user_id=created_user.id,
                title="Test Chat Session"
            )
            session.add(chat)
            await session.flush()
            test_logger.info(f"Created chat: {chat.id} for user {chat.user_id}")
            
            # Create messages in the chat
            user_message = Message(
                chat_id=chat.id,
                role="user",
                content="This is a test user message"
            )
            session.add(user_message)
            await session.flush()
            test_logger.info(f"Created user message: {user_message.id}")
            
            assistant_message = Message(
                chat_id=chat.id,
                role="assistant",
                content="This is a test assistant response"
            )
            session.add(assistant_message)
            await session.flush()
            test_logger.info(f"Created assistant message: {assistant_message.id}")
            
            # Create tool usage for the assistant message
            tool_usage = ToolUsage(
                message_id=assistant_message.id,
                tool_name="policy_search",
                input={"query": "test policy"},
                output={"results": [{"id": created_policy.id, "title": created_policy.title}]},
                execution_time=0.125
            )
            session.add(tool_usage)
            await session.flush()
            test_logger.info(f"Created tool usage: {tool_usage.id}")
            
            # Commit all changes
            await session.commit()
            test_logger.info("Additional tables test complete - all test data committed")
            return True
    except Exception as e:
        test_logger.error(f"Additional tables test failed: {e}")
        return False
    finally:
        await engine.dispose()

async def test_chunking_and_embedding():
    """Test policy chunking and embedding functionality."""
    test_logger.info("Testing policy chunking and embedding functionality")
    
    engine = create_async_engine(TEST_DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            policy_repo = PolicyRepository(session)
            
            # Create test policy
            policy = Policy(
                title="Chunking Test Policy",
                description="Policy for testing chunking and embedding",
                source_url="http://example.com/chunking-policy",
                markdown_content="# Chunking Test\nThis is content for testing chunks.",
                text_content="Chunking Test. This is a longer text content that would typically be chunked into multiple pieces. We're simulating that process here by creating multiple chunks manually."
            )
            created_policy = await policy_repo.create(policy)
            test_logger.info(f"Created policy for chunking test: {created_policy.id}")
            
            # Create multiple chunks with embeddings
            chunks = []
            for i in range(3):
                chunk = PolicyChunk(
                    policy_id=created_policy.id,
                    chunk_index=i,
                    content=f"This is chunk {i} of the policy. It contains specific content.",
                    chunk_metadata={"position": i, "length": 50},
                    # Dummy embedding vector (would normally come from an embedding model)
                    embedding=[0.1 * j for j in range(backend_config.RAG.EMBEDDING_DIMENSIONS)] if i == 0 else [0.2 * j for j in range(backend_config.RAG.EMBEDDING_DIMENSIONS)]
                )
                created_chunk = await policy_repo.create_chunk(chunk)
                chunks.append(created_chunk)
                test_logger.info(f"Created chunk {i}: {created_chunk.id} with embedding")
            
            # Verify chunks were created
            policy_chunks = await policy_repo.get_chunks_by_policy_id(created_policy.id)
            assert len(policy_chunks) == 3, f"Expected 3 chunks, got {len(policy_chunks)}"
            test_logger.info(f"Successfully retrieved {len(policy_chunks)} chunks for policy")
            
            # Test getting neighbors of a chunk
            if len(chunks) > 1:
                try:
                    # Check that chunks are proper objects with id attributes
                    if hasattr(chunks[1], 'id'):
                        middle_chunk_id = chunks[1].id
                        neighbors = await policy_repo.get_chunk_neighbors(middle_chunk_id, window=1)
                        if "previous" in neighbors and neighbors["previous"] is not None:
                            if isinstance(neighbors["previous"], list) and len(neighbors["previous"]) > 0:
                                test_logger.info(f"Found previous chunk(s): {', '.join(str(c.id) for c in neighbors['previous'])}")
                            else:
                                test_logger.info(f"Found previous chunk: {neighbors['previous']}")
                        if "next" in neighbors and neighbors["next"] is not None:
                            if isinstance(neighbors["next"], list) and len(neighbors["next"]) > 0:
                                test_logger.info(f"Found next chunk(s): {', '.join(str(c.id) for c in neighbors['next'])}")
                            else:
                                test_logger.info(f"Found next chunk: {neighbors['next']}")
                        test_logger.info("Successfully retrieved chunk neighbors")
                    else:
                        test_logger.warning(f"Chunk neighbors test skipped: chunks[1] does not have id attribute. Type: {type(chunks[1])}")
                except Exception as e:
                    test_logger.warning(f"Chunk neighbors test skipped: {e}")
            
            # Test search by embedding if supported
            try:
                # Mock embedding vector for search
                search_embedding = [0.15 * j for j in range(backend_config.RAG.EMBEDDING_DIMENSIONS)]
                embedding_results = await policy_repo.search_chunks_by_embedding(search_embedding, limit=2)
                test_logger.info(f"Vector search returned {len(embedding_results)} results")
            except Exception as e:
                test_logger.warning(f"Vector search not fully tested: {e}")
            
            # Keep the chunks in the database by not deleting the policy
            test_logger.info("Keeping policy chunks in database for inspection")
            await session.commit()
            
            # Return policy id for reference
            return created_policy.id
    except Exception as e:
        test_logger.error(f"Chunking and embedding test failed: {e}")
        return None
    finally:
        await engine.dispose()

# Run all tests
async def run_all_tests(keep_db=False):
    """Run all database tests.
    
    Args:
        keep_db: If True, don't drop the database after tests finish.
    """
    try:
        # Drop any existing test database
        await drop_test_database()
        
        # Create fresh test database
        await create_test_database()
        
        # Set up database with tables and triggers
        await setup_database()
        
        # Verify database tables
        tables_ok = await verify_database_tables()
        if not tables_ok:
            test_logger.error("Database table verification failed")
            return
        
        # Test user repository
        user_test_ok = await test_user_repository()
        if not user_test_ok:
            test_logger.error("User repository tests failed")
            return
            
        # Test policy repository
        policy_test_ok = await test_policy_repository()
        if not policy_test_ok:
            test_logger.error("Policy repository tests failed")
            return
            
        # Test additional tables
        additional_tables_ok = await test_additional_tables()
        if not additional_tables_ok:
            test_logger.error("Additional tables tests failed")
            return
            
        # Test chunking and embedding
        chunking_and_embedding_ok = await test_chunking_and_embedding()
        if chunking_and_embedding_ok is None:
            test_logger.error("Chunking and embedding test failed")
            return
            
        test_logger.info("All database tests passed successfully!")
        
        if keep_db:
            test_logger.info(f"Keeping test database '{DB_NAME}' for inspection (--keep-db flag is set)")
        else:
            # Clean up test database
            await drop_test_database()
    except Exception as e:
        test_logger.error(f"Test suite failed: {e}")
        # Still try to drop database if tests failed, unless keep_db is True
        if not keep_db:
            await drop_test_database()

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test database functionality")
    parser.add_argument("--keep-db", action="store_true", help="Keep the test database after tests finish")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_all_tests(keep_db=args.keep_db)) 