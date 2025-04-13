# ydrpolicy/backend/database/init_db.py
import asyncio
from datetime import datetime
import logging
import os
import re
from typing import Optional, Set, Dict
from urllib.parse import urlparse
import pandas as pd
import asyncpg
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession

from ydrpolicy.backend.database.models import (
    Base,
    Policy,
    PolicyChunk,
    Image,
    create_search_vector_trigger,
)
from ydrpolicy.backend.database.engine import get_async_session, get_async_engine
from ydrpolicy.backend.database.repository.policies import PolicyRepository
from ydrpolicy.backend.services.chunking import chunk_text
from ydrpolicy.backend.services.embeddings import embed_texts
from ydrpolicy.backend.config import config

# Initialize logger
logger = logging.getLogger(__name__)

from ydrpolicy.backend.utils.paths import ensure_directories


async def create_database(db_url: str) -> bool:
    """
    Create the database if it doesn't exist.

    Args:
        db_url: The database URL in SQLAlchemy format.

    Returns:
        bool: True if database was created or already existed, False on error.
    """
    # Parse the database URL to get components
    if db_url.startswith("postgresql+asyncpg://"):
        # Remove the driver prefix for asyncpg
        db_url_parsed = db_url.replace("postgresql+asyncpg://", "postgresql://")
    else:
        db_url_parsed = db_url

    try:
        parsed = urlparse(db_url_parsed)
        db_name = parsed.path.lstrip("/")
        if not db_name:
            logger.error("Database name could not be parsed from URL.")
            return False

        # Construct the postgres admin URL (no specific database)
        admin_url = f"{parsed.scheme}://{parsed.netloc}/postgres"

        logger.info(f"Checking if database '{db_name}' exists...")

        conn = None  # Initialize conn to None
        try:
            # Connect to the postgres database
            conn = await asyncpg.connect(admin_url)

            # Check if the database exists
            result = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )

            if not result:
                logger.info(f"Creating database '{db_name}'...")
                # Use CREATE DATABASE command
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"SUCCESS: Database '{db_name}' created.")
            else:
                logger.info(f"Database '{db_name}' already exists.")

            return True  # Indicate success (created or existed)

        except asyncpg.exceptions.InvalidCatalogNameError:
            logger.error(
                f"Database '{db_name}' does not exist (caught InvalidCatalogNameError). Cannot connect directly."
            )
            # Attempt creation via admin connection if not already done
            if conn is None:  # Check if we failed before even connecting
                try:
                    conn_admin = await asyncpg.connect(admin_url)
                    logger.info(
                        f"Re-attempting database creation for '{db_name}' via admin connection..."
                    )
                    await conn_admin.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"SUCCESS: Database '{db_name}' created.")
                    await conn_admin.close()
                    return True
                except Exception as create_err:
                    logger.error(
                        f"Failed to create database '{db_name}' via admin connection: {create_err}"
                    )
                    return False
            else:
                # This case shouldn't normally be reached if creation logic is sound
                logger.error(
                    f"Database '{db_name}' seems not to exist, but creation logic didn't run as expected."
                )
                return False

        except Exception as e:
            logger.error(f"Error checking/creating database '{db_name}': {e}")
            # Consider re-raising specific errors if needed upstream
            return False
        finally:
            if conn:
                await conn.close()

    except Exception as parse_err:
        logger.error(f"Error parsing database URL '{db_url}': {parse_err}")
        return False


async def create_extension(engine: AsyncEngine, extension_name: str) -> None:
    """
    Create a PostgreSQL extension if it doesn't exist.

    Args:
        engine: SQLAlchemy AsyncEngine object.
        extension_name: Name of the extension to create.
    """
    logger.info(f"Ensuring extension '{extension_name}' exists...")
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"CREATE EXTENSION IF NOT EXISTS {extension_name} SCHEMA public"
                )  # Specify schema
            )
        logger.info(f"Extension '{extension_name}' checked/created.")
    except Exception as e:
        logger.error(f"Error creating extension '{extension_name}': {e}")
        # Depending on the error, you might want to raise it or handle it
        # For example, permission errors might need manual intervention.
        # If the extension is critical, consider raising the error.
        # raise e


async def create_tables(engine: AsyncEngine) -> None:
    """
    Create all database tables defined in the models.

    Args:
        engine: SQLAlchemy AsyncEngine object.
    """
    logger.info("Creating database tables if they don't exist...")
    try:
        async with engine.begin() as conn:
            # Create all tables defined in Base.metadata
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables checked/created.")

        # Apply triggers after tables are created
        logger.info("Applying search vector triggers...")
        async with engine.connect() as conn:
            # Execute each SQL statement separately
            for statement in create_search_vector_trigger():
                await conn.execute(text(statement))
            await conn.commit()  # Commit trigger creation
        logger.info("Search vector triggers applied.")

    except Exception as e:
        logger.error(f"Error creating tables or applying triggers: {e}")
        # This is likely a critical error, so re-raise
        raise e


async def get_existing_policies_info(session: AsyncSession) -> Dict[str, Dict]:
    """Fetches all existing policy titles and their metadata from the database."""
    logger.info("Fetching existing policy information from database...")
    # Use correct column name policy_metadata
    stmt = select(Policy.id, Policy.title, Policy.policy_metadata)
    result = await session.execute(stmt)

    # Create a dictionary mapping title to metadata
    policies_info = {}
    for id, title, metadata in result:
        policies_info[title] = {"id": id, "metadata": metadata}

    logger.info(f"Found {len(policies_info)} existing policies in database.")
    return policies_info


async def process_new_policy_folder(
    folder_path: str,
    policy_title: str,
    scrape_timestamp: str,
    session: AsyncSession,
    policy_repo: PolicyRepository,
    extraction_reasoning: Optional[str] = None,
):
    """Processes a single new policy folder and adds its data to the DB."""
    logger.info(
        f"Processing new policy: '{policy_title}' from folder: {os.path.basename(folder_path)}"
    )

    md_path = os.path.join(folder_path, "content.md")
    txt_path = os.path.join(folder_path, "content.txt")

    if not os.path.exists(md_path):
        logger.error(f"  Markdown file not found: {md_path}. Skipping policy.")
        return
    if not os.path.exists(txt_path):
        logger.error(f"  Text file not found: {txt_path}. Skipping policy.")
        return

    try:
        # 1. Read content files
        with open(md_path, "r", encoding="utf-8") as f_md:
            markdown_content = f_md.read()
        with open(txt_path, "r", encoding="utf-8") as f_txt:
            text_content = f_txt.read()
        logger.debug(
            f"  Read content.md ({len(markdown_content)} chars) and content.txt ({len(text_content)} chars)."
        )

        # 2. Create Policy object
        # Try to extract source URL from markdown header if possible
        source_url_match = re.search(
            r"^# Source URL: (.*)$", markdown_content, re.MULTILINE
        )
        source_url = source_url_match.group(1).strip() if source_url_match else None

        policy = Policy(
            title=policy_title,
            source_url=source_url,
            markdown_content=markdown_content,
            text_content=text_content,
            description=extraction_reasoning,  # Use extraction_reasoning as description
            policy_metadata={
                "scrape_timestamp": scrape_timestamp,
                "source_folder": os.path.basename(folder_path),
                "processed_at": datetime.utcnow().isoformat(),
            },
            # created_at and updated_at will use database defaults
        )
        # Add policy to session and flush to get ID
        # policy = await policy_repo.create(policy) # Use repository method
        session.add(policy)
        await session.flush()
        await session.refresh(policy)  # Ensure ID and defaults are loaded
        logger.info(f"SUCCESS: Created Policy record with ID: {policy.id}")

        # 3. Process and add Images
        image_files = [
            f
            for f in os.listdir(folder_path)
            if f.lower().startswith("img-")
            and f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
        ]
        image_count = 0
        for img_filename in image_files:
            try:
                image = Image(
                    policy_id=policy.id,
                    filename=img_filename,
                    relative_path=img_filename,  # Path relative to policy folder
                    # created_at will use database default
                )
                session.add(image)
                image_count += 1
            except Exception as img_err:
                logger.error(
                    f"  Error creating Image object for '{img_filename}': {img_err}"
                )
        if image_count > 0:
            await session.flush()  # Flush images together
            logger.info(f"  Added {image_count} Image records.")

        # 4. Chunk Text Content
        chunks = chunk_text(
            text=text_content,
            chunk_size=config.RAG.CHUNK_SIZE,
            chunk_overlap=config.RAG.CHUNK_OVERLAP,
        )
        logger.info(f"  Split text content into {len(chunks)} chunks.")

        if not chunks:
            logger.warning(
                f"  No chunks generated for policy '{policy_title}'. Skipping embedding and chunk creation."
            )
            return  # Nothing more to do for this policy

        # 5. Generate Embeddings (in batches if possible)
        try:
            embeddings = await embed_texts(chunks)
            if len(embeddings) != len(chunks):
                raise ValueError(
                    f"Number of embeddings ({len(embeddings)}) does not match number of chunks ({len(chunks)})."
                )
            logger.info(f"  Generated {len(embeddings)} embeddings.")
        except Exception as emb_err:
            logger.error(
                f"  Failed to generate embeddings for policy '{policy_title}': {emb_err}. Skipping chunk creation."
            )
            # Optionally, rollback the policy creation or mark it as incomplete
            # For now, we just skip chunk/embedding creation for this policy
            # Consider raising the error if embeddings are critical for all policies
            return

        # 6. Create PolicyChunk objects
        chunk_count = 0
        for i, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                chunk = PolicyChunk(
                    policy_id=policy.id,
                    chunk_index=i,
                    content=chunk_content,
                    embedding=embedding,
                    # created_at will use database default
                )
                session.add(chunk)
                chunk_count += 1
            except Exception as chunk_err:
                logger.error(
                    f"  Error creating PolicyChunk object for index {i}: {chunk_err}"
                )
        if chunk_count > 0:
            logger.info(f"  Added {chunk_count} PolicyChunk records to session.")

    except FileNotFoundError as fnf_err:
        logger.error(
            f"  File not found during processing of '{policy_title}': {fnf_err}"
        )
    except IntegrityError as ie:
        # This might happen if the unique constraint on title is violated
        # despite our initial check (e.g., race condition in parallel processing)
        logger.error(
            f"  Database integrity error (likely duplicate title) for '{policy_title}': {ie}"
        )
        # Rollback might be needed here if not handled by the outer context manager
    except Exception as e:
        logger.error(
            f"  Unexpected error processing policy '{policy_title}': {e}", exc_info=True
        )
        # Depending on the severity, consider rolling back or raising


async def populate_database_from_scraped_policies():
    """
    Scans the scraped policies directory, identifies new policies,
    and populates the database with their content, chunks, images, and embeddings.
    """
    # Use the scraped policies directory defined in config
    scraped_policies_dir = config.PATHS.SCRAPED_POLICIES_DIR
    if not os.path.isdir(scraped_policies_dir):
        logger.error(f"Scraped policies directory not found: {scraped_policies_dir}")
        return

    logger.info(f"Scanning scraped policies directory: {scraped_policies_dir}")

    # Create mappings from both timestamp and URL to extraction_reasoning from the CSV file
    timestamp_to_description = {}
    url_to_description = {}
    csv_path = os.path.join(
        config.PATHS.PROCESSED_DATA_DIR, "processed_policies_log.csv"
    )
    if os.path.exists(csv_path):
        try:
            logger.info(f"Reading policy descriptions from CSV: {csv_path}")
            policy_df = pd.read_csv(csv_path)

            # Check which columns we have available
            required_columns = ["extraction_reasoning"]
            timestamp_mapping = "timestamp" in policy_df.columns
            url_mapping = "url" in policy_df.columns

            if "extraction_reasoning" in policy_df.columns:
                for _, row in policy_df.iterrows():
                    if pd.notna(row["extraction_reasoning"]):
                        reasoning = row["extraction_reasoning"]

                        # Create timestamp mapping if column exists
                        if timestamp_mapping and pd.notna(row["timestamp"]):
                            timestamp = str(row["timestamp"])
                            timestamp_to_description[timestamp] = reasoning

                        # Create URL mapping if column exists
                        if url_mapping and pd.notna(row["url"]):
                            url = row["url"]
                            url_to_description[url] = reasoning

                logger.info(
                    f"Loaded {len(timestamp_to_description)} timestamp mappings and {len(url_to_description)} URL mappings for policy descriptions"
                )
            else:
                logger.warning(
                    f"CSV file missing extraction_reasoning column. Found: {policy_df.columns.tolist()}"
                )
        except Exception as e:
            logger.error(f"Error reading policy descriptions from CSV: {e}")
    else:
        logger.warning(f"Policy descriptions CSV file not found: {csv_path}")

    # Process each folder inside the scraped policies directory.
    # Folders are expected to be named as <title>_<timestamp>
    # where timestamp is a 20 digit number
    # Regex pattern for folder name: <title>_<timestamp>
    # Title can contain underscores, the timestamp is after the last underscore
    folder_pattern = re.compile(r"^(.+)_(\d{20})$")
    processed_count = 0
    skipped_count = 0

    async with get_async_session() as session:
        try:
            policy_repo = PolicyRepository(session)  # Instantiate repository
            existing_policies = await get_existing_policies_info(session)

            for folder_name in os.listdir(scraped_policies_dir):
                folder_path = os.path.join(scraped_policies_dir, folder_name)
                if not os.path.isdir(folder_path):
                    continue  # Skip files, only process directories

                match = folder_pattern.match(folder_name)
                if not match:
                    logger.warning(
                        f"Skipping folder with unexpected name format: {folder_name}"
                    )
                    logger.debug(
                        f"Folder name '{folder_name}' did not match expected pattern '^(.+)_(\\d{{20}})$'"
                    )
                    skipped_count += 1
                    continue

                policy_title = match.group(1)
                scrape_timestamp = match.group(2)  # Extracted timestamp string
                logger.debug(
                    f"Matched folder name: '{folder_name}' → title='{policy_title}', timestamp={scrape_timestamp}"
                )

                # Check if policy exists and if this is a newer version
                should_process = True
                if policy_title in existing_policies:
                    # Check if this is a newer version based on timestamp
                    existing_metadata = existing_policies[policy_title].get(
                        "metadata", {}
                    )
                    if existing_metadata and "scrape_timestamp" in existing_metadata:
                        existing_timestamp = existing_metadata["scrape_timestamp"]
                        if existing_timestamp >= scrape_timestamp:
                            logger.debug(
                                f"Skipping older or same version of policy: '{policy_title}', existing={existing_timestamp}, new={scrape_timestamp}"
                            )
                            skipped_count += 1
                            should_process = False
                        else:
                            logger.info(
                                f"Found newer version of policy: '{policy_title}', existing={existing_timestamp}, new={scrape_timestamp}"
                            )
                            # We'll process this newer version, but first delete the old one
                            existing_id = existing_policies[policy_title]["id"]
                            logger.info(
                                f"Deleting old version of policy with ID: {existing_id}"
                            )
                            await policy_repo.delete_by_id(existing_id)
                    else:
                        # No timestamp in metadata, consider it as potentially new
                        logger.debug(
                            f"Existing policy '{policy_title}' has no timestamp metadata. Will replace it."
                        )
                        existing_id = existing_policies[policy_title]["id"]
                        await policy_repo.delete_by_id(existing_id)

                if should_process:
                    # First try to get extraction reasoning using timestamp
                    extraction_reasoning = timestamp_to_description.get(
                        scrape_timestamp
                    )

                    # If not found by timestamp, try to get source URL from markdown and use it to look up
                    if not extraction_reasoning and url_to_description:
                        # Check markdown file for source URL
                        md_path = os.path.join(folder_path, "content.md")
                        if os.path.exists(md_path):
                            try:
                                with open(md_path, "r", encoding="utf-8") as f_md:
                                    markdown_content = f_md.read()
                                    # Extract source URL
                                    source_url_match = re.search(
                                        r"^# Source URL: (.*)$",
                                        markdown_content,
                                        re.MULTILINE,
                                    )
                                    if source_url_match:
                                        source_url = source_url_match.group(1).strip()
                                        extraction_reasoning = url_to_description.get(
                                            source_url
                                        )
                                        if extraction_reasoning:
                                            logger.debug(
                                                f"Found description via URL matching for '{source_url}'"
                                            )
                            except Exception as file_err:
                                logger.error(
                                    f"Error reading markdown file for URL extraction: {file_err}"
                                )

                    if extraction_reasoning:
                        logger.debug(
                            f"Found description for policy: {extraction_reasoning[:50]}..."
                        )
                    else:
                        logger.debug(
                            f"No description found for policy in folder '{folder_name}'"
                        )

                    # Process the new policy folder
                    await process_new_policy_folder(
                        folder_path=folder_path,
                        policy_title=policy_title,
                        scrape_timestamp=scrape_timestamp,
                        session=session,
                        policy_repo=policy_repo,  # Pass repository
                        extraction_reasoning=extraction_reasoning,
                    )
                    # Update our tracking of existing policies
                    processed_count += 1

            # Commit all changes made within the session context manager
            # No explicit commit needed here due to 'async with get_async_session()'

        except Exception as e:
            logger.error(f"Error during database population: {e}", exc_info=True)
            # The context manager `get_async_session` will handle rollback
            raise  # Re-raise the error to indicate failure

    logger.info(
        f"Database population finished. Processed {processed_count} new policies. Skipped {skipped_count} folders."
    )


async def init_db(db_url: Optional[str] = None, populate: bool = True) -> None:
    """
    Initialize the database: create DB, extensions, tables, and optionally populate.

    Args:
        db_url: Optional database URL. If not provided, uses the URL from config.
        populate: If True, scan processed data dir and populate new policies.
    """
    # Ensure all required directories defined in config.PATHS exist
    ensure_directories()

    db_url = db_url or str(config.DATABASE.DATABASE_URL)
    logger.info(f"Starting database initialization for: {db_url}")

    # 1. Ensure the database itself exists
    db_exists_or_created = await create_database(db_url)
    if not db_exists_or_created:
        logger.critical(
            f"Failed to ensure database exists at {db_url}. Aborting initialization."
        )
        return  # Stop if database creation/verification failed

    # 2. Create engine to connect to the specific database
    engine = create_async_engine(
        db_url, echo=config.API.DEBUG
    )  # Use debug setting for echo

    try:
        # 3. Create required PostgreSQL extensions (e.g., vector)
        # Use public schema explicitly if needed
        await create_extension(engine, "vector")

        # 4. Create all tables defined in models.py
        await create_tables(engine)

        # 5. Optionally, populate the database from processed data
        if populate:
            logger.info("Starting data population from scraped_policies directory...")
            await populate_database_from_scraped_policies()
        else:
            logger.info("Skipping data population step.")

        logger.info("SUCCESS: Database initialization completed successfully.")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
    finally:
        # Dispose of the engine connection pool
        await engine.dispose()
        logger.info("Database engine disposed.")


async def drop_db(db_url: Optional[str] = None, force: bool = False) -> None:
    """
    Drop the database. USE WITH CAUTION!

    Args:
        db_url: Optional database URL. If not provided, uses the URL from config.
        force: If True, skip confirmation prompt (use for automated tests)
    """
    db_url = db_url or str(config.DATABASE.DATABASE_URL)

    # Parse the database URL to get components
    if db_url.startswith("postgresql+asyncpg://"):
        # Remove the driver prefix for asyncpg
        db_url_parsed = db_url.replace("postgresql+asyncpg://", "postgresql://")
    else:
        db_url_parsed = db_url

    try:
        parsed = urlparse(db_url_parsed)
        db_name = parsed.path.lstrip("/")
        if not db_name:
            logger.error("Database name could not be parsed from URL for dropping.")
            return

        # Construct the postgres admin URL (no specific database)
        admin_url = f"{parsed.scheme}://{parsed.netloc}/postgres"

        logger.warning(
            f"Attempting to drop database '{db_name}'... THIS WILL DELETE ALL DATA!"
        )

        # Skip confirmation if force=True
        if not force:
            confirm = input(
                f"Are you sure you want to drop database '{db_name}'? (yes/no): "
            )
            if confirm.lower() != "yes":
                logger.info("Database drop cancelled.")
                return

        conn = None
        try:
            # Connect to the postgres database
            conn = await asyncpg.connect(admin_url)

            # Force disconnect all active connections to the target database
            logger.info(f"Terminating active connections to '{db_name}'...")
            await conn.execute(
                f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = $1
                AND pid <> pg_backend_pid();
            """,
                db_name,
            )
            logger.info("Connections terminated.")

            # Drop the database
            logger.info(f"Dropping database '{db_name}'...")
            await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')

            logger.info(f"SUCCESS: Database '{db_name}' dropped successfully.")
        except Exception as e:
            logger.error(f"Error dropping database '{db_name}': {e}")
            # Consider raising specific errors if needed
        finally:
            if conn:
                await conn.close()

    except Exception as parse_err:
        logger.error(f"Error parsing database URL '{db_url}' for dropping: {parse_err}")


# Main execution block for running the script directly
if __name__ == "__main__":
    # Example usage: python -m ydrpolicy.backend.database.init_db [--populate | --drop]
    import argparse

    parser = argparse.ArgumentParser(
        description="Initialize or drop the YDR Policy RAG database."
    )
    parser.add_argument(
        "--populate",
        action="store_true",
        help="Populate the database with new policies found in the processed data directory.",
    )
    parser.add_argument(
        "--drop", action="store_true", help="Drop the database (USE WITH CAUTION!)."
    )
    parser.add_argument("--db_url", help="Optional database URL to override config.")
    parser.add_argument(
        "--no-populate",
        action="store_true",
        help="Explicitly skip the population step during initialization.",
    )

    args = parser.parse_args()

    # Determine if population should run
    should_populate = args.populate or (not args.drop and not args.no_populate)

    if args.drop:
        # Run the drop function
        asyncio.run(drop_db(db_url=args.db_url))
    else:
        # Run the initialization function
        asyncio.run(init_db(db_url=args.db_url, populate=should_populate))
