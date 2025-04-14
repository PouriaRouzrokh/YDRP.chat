# ydrpolicy/backend/database/init_db.py
import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import asyncpg
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,  # Keep this import
    create_async_engine,
)

# Local Application Imports
from ydrpolicy.backend.config import config
from ydrpolicy.backend.database.engine import get_async_session  # Still used for seeding/populating
from ydrpolicy.backend.database.models import (
    Base,
    Image,
    Policy,
    PolicyChunk,
    User,
    create_search_vector_trigger,
)
from ydrpolicy.backend.database.repository.policies import PolicyRepository
from ydrpolicy.backend.database.repository.users import UserRepository
from ydrpolicy.backend.services.chunking import chunk_text
from ydrpolicy.backend.services.embeddings import embed_texts
from ydrpolicy.backend.utils.auth_utils import hash_password
from ydrpolicy.backend.utils.paths import ensure_directories

# Initialize logger
logger = logging.getLogger(__name__)


# (Keep create_database function - unchanged)
async def create_database(db_url: str) -> bool:
    """Creates the database if it doesn't exist."""
    # ... (existing code) ...
    if db_url.startswith("postgresql+asyncpg://"):
        db_url_parsed = db_url.replace("postgresql+asyncpg://", "postgresql://")
    else:
        db_url_parsed = db_url
    try:
        parsed = urlparse(db_url_parsed)
        db_name = parsed.path.lstrip("/")
        if not db_name:
            logger.error("Database name could not be parsed from URL.")
            return False
        admin_url = f"{parsed.scheme}://{parsed.netloc}/postgres"
        logger.info(f"Checking if database '{db_name}' exists...")
        conn = None
        try:
            conn = await asyncpg.connect(admin_url)
            result = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
            if not result:
                logger.info(f"Creating database '{db_name}'...")
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"SUCCESS: Database '{db_name}' created.")
            else:
                logger.info(f"Database '{db_name}' already exists.")
            return True
        except asyncpg.exceptions.InvalidCatalogNameError:
            logger.debug(f"Database '{db_name}' does not exist (InvalidCatalogNameError). Will attempt creation.")
            if conn is None:
                try:
                    conn_admin = await asyncpg.connect(admin_url)
                    logger.info(f"Re-attempting creation for '{db_name}' via admin connection...")
                    await conn_admin.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"SUCCESS: Database '{db_name}' created.")
                    await conn_admin.close()
                    return True
                except Exception as create_err:
                    logger.error(f"Failed to create '{db_name}' via admin: {create_err}")
                    return False
            else:
                try:
                    logger.info(f"Creating database '{db_name}' using existing admin connection...")
                    await conn.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"SUCCESS: Database '{db_name}' created.")
                    return True
                except Exception as create_err:
                    logger.error(f"Failed to create '{db_name}' using existing admin: {create_err}")
                    return False
        except Exception as e:
            logger.error(f"Error checking/creating database '{db_name}': {e}")
            return False
        finally:
            if conn:
                await conn.close()
    except Exception as parse_err:
        logger.error(f"Error parsing database URL '{db_url}': {parse_err}")
        return False


# (Keep create_extension function - unchanged)
async def create_extension(engine: AsyncEngine, extension_name: str) -> None:
    """Creates a PostgreSQL extension if it doesn't exist."""
    logger.info(f"Ensuring extension '{extension_name}' exists...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {extension_name} SCHEMA public"))
        logger.info(f"Extension '{extension_name}' checked/created.")
    except Exception as e:
        logger.error(f"Error creating extension '{extension_name}': {e}. Continuing...")


# (Keep seed_users_from_json function - unchanged)
async def seed_users_from_json(session: AsyncSession):
    """Reads users from users.json and creates them if they don't exist."""
    # ... (existing code) ...
    seed_file_path = config.PATHS.USERS_SEED_FILE
    logger.info(f"Attempting to seed users from: {seed_file_path}")
    if not os.path.exists(seed_file_path):
        logger.warning(f"User seed file not found at '{seed_file_path}'. Skipping.")
        return
    try:
        with open(seed_file_path, "r") as f:
            users_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from '{seed_file_path}': {e}. Skipping.")
        return
    except Exception as e:
        logger.error(f"Error reading user seed file '{seed_file_path}': {e}. Skipping.")
        return
    if not isinstance(users_data, list):
        logger.error(f"User seed file '{seed_file_path}' should contain a JSON list. Skipping.")
        return

    user_repo = UserRepository(session)
    created_count = 0
    skipped_count = 0
    for user_info in users_data:
        if not isinstance(user_info, dict):
            logger.warning(f"Skipping invalid user entry (not a dict): {user_info}")
            continue
        email = user_info.get("email")
        full_name = user_info.get("full_name")
        plain_password = user_info.get("password")
        is_admin = user_info.get("is_admin", False)
        if not email or not full_name or not plain_password:
            logger.warning(f"Skipping user entry missing fields: {user_info}")
            continue
        existing_user = await user_repo.get_by_email(email)
        if existing_user:
            logger.debug(f"User '{email}' already exists. Skipping.")
            skipped_count += 1
            continue
        try:
            hashed_pw = hash_password(plain_password)
            new_user = User(email=email, full_name=full_name, password_hash=hashed_pw, is_admin=is_admin)
            session.add(new_user)
            logger.info(f"Prepared new user for creation: {email} (Admin: {is_admin})")
            created_count += 1
        except Exception as e:
            logger.error(f"Error preparing user '{email}' for creation: {e}")
    logger.info(f"User seeding complete. Prepared: {created_count}, Skipped: {skipped_count}")


# (Keep get_existing_policies_info function - unchanged)
async def get_existing_policies_info(session: AsyncSession) -> Dict[str, Dict]:
    """Fetches existing policy titles and their metadata."""
    # ... (existing code) ...
    logger.info("Fetching existing policy information from database...")
    stmt = select(Policy.id, Policy.title, Policy.policy_metadata)
    result = await session.execute(stmt)
    policies_info = {title: {"id": id, "metadata": metadata} for id, title, metadata in result}
    logger.info(f"Found {len(policies_info)} existing policies in database.")
    return policies_info


# (Keep process_new_policy_folder function - unchanged)
async def process_new_policy_folder(
    folder_path: str,
    policy_title: str,
    scrape_timestamp: str,
    session: AsyncSession,
    policy_repo: PolicyRepository,
    extraction_reasoning: Optional[str] = None,
):
    """Processes a single new policy folder and adds its data to the DB."""
    # ... (existing code) ...
    logger.info(f"Processing new policy: '{policy_title}' from folder: {os.path.basename(folder_path)}")
    md_path = os.path.join(folder_path, "content.md")
    txt_path = os.path.join(folder_path, "content.txt")
    if not os.path.exists(md_path):
        logger.error(f"  Markdown file not found: {md_path}. Skipping.")
        return
    if not os.path.exists(txt_path):
        logger.error(f"  Text file not found: {txt_path}. Skipping.")
        return
    try:
        with open(md_path, "r", encoding="utf-8") as f_md:
            markdown_content = f_md.read()
        with open(txt_path, "r", encoding="utf-8") as f_txt:
            text_content = f_txt.read()
        logger.debug(f"  Read content files.")
        source_url_match = re.search(r"^# Source URL: (.*)$", markdown_content, re.MULTILINE)
        source_url = source_url_match.group(1).strip() if source_url_match else None
        policy = Policy(
            title=policy_title,
            source_url=source_url,
            markdown_content=markdown_content,
            text_content=text_content,
            description=extraction_reasoning,
            policy_metadata={
                "scrape_timestamp": scrape_timestamp,
                "source_folder": os.path.basename(folder_path),
                "processed_at": datetime.utcnow().isoformat(),
            },
        )
        session.add(policy)
        await session.flush()
        await session.refresh(policy)
        logger.info(f"SUCCESS: Created Policy record ID: {policy.id}")
        image_files = [
            f
            for f in os.listdir(folder_path)
            if f.lower().startswith("img-") and f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
        ]
        image_count = 0
        for img_filename in image_files:
            try:
                session.add(Image(policy_id=policy.id, filename=img_filename, relative_path=img_filename))
                image_count += 1
            except Exception as img_err:
                logger.error(f"  Error creating Image object for '{img_filename}': {img_err}")
        if image_count > 0:
            await session.flush()
            logger.info(f"  Added {image_count} Image records.")
        chunks = chunk_text(text=text_content, chunk_size=config.RAG.CHUNK_SIZE, chunk_overlap=config.RAG.CHUNK_OVERLAP)
        logger.info(f"  Split text into {len(chunks)} chunks.")
        if not chunks:
            logger.warning(f"  No chunks generated for '{policy_title}'.")
            return
        try:
            embeddings = await embed_texts(chunks)
            if len(embeddings) != len(chunks):
                raise ValueError("Embeddings/chunks count mismatch.")
            logger.info(f"  Generated {len(embeddings)} embeddings.")
        except Exception as emb_err:
            logger.error(f"  Embedding failed for '{policy_title}': {emb_err}.")
            return
        chunk_count = 0
        for i, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                session.add(PolicyChunk(policy_id=policy.id, chunk_index=i, content=chunk_content, embedding=embedding))
                chunk_count += 1
            except Exception as chunk_err:
                logger.error(f"  Error creating PolicyChunk index {i}: {chunk_err}")
        if chunk_count > 0:
            await session.flush()
            logger.info(f"  Added {chunk_count} PolicyChunk records.")
    except FileNotFoundError as fnf_err:
        logger.error(f"  File not found processing '{policy_title}': {fnf_err}")
    except IntegrityError as ie:
        logger.error(f"  DB integrity error (duplicate title?) for '{policy_title}': {ie}")
        raise ie
    except Exception as e:
        logger.error(f"  Unexpected error processing policy '{policy_title}': {e}", exc_info=True)
        raise e


# (Keep populate_database_from_scraped_policies function - unchanged, it uses the passed session)
async def populate_database_from_scraped_policies(session: AsyncSession):
    """
    Scans the scraped policies directory, identifies new/updated policies,
    and populates the database within the given session.
    """
    # ... (existing code using the passed 'session') ...
    scraped_policies_dir = config.PATHS.SCRAPED_POLICIES_DIR
    if not os.path.isdir(scraped_policies_dir):
        logger.error(f"Scraped policies directory not found: {scraped_policies_dir}")
        return
    logger.info(f"Scanning scraped policies directory: {scraped_policies_dir}")
    timestamp_to_description = {}
    url_to_description = {}
    csv_path = os.path.join(config.PATHS.PROCESSED_DATA_DIR, "processed_policies_log.csv")
    if os.path.exists(csv_path):
        try:
            policy_df = pd.read_csv(csv_path)
            logger.info(f"Reading policy descriptions from CSV: {csv_path}")
            timestamp_mapping = "timestamp" in policy_df.columns
            url_mapping = "url" in policy_df.columns
            if "extraction_reasoning" in policy_df.columns:
                for _, row in policy_df.iterrows():
                    if pd.notna(row["extraction_reasoning"]):
                        reasoning = row["extraction_reasoning"]
                        if timestamp_mapping and pd.notna(row["timestamp"]):
                            timestamp_to_description[str(row["timestamp"])] = reasoning
                        if url_mapping and pd.notna(row["url"]):
                            url_to_description[row["url"]] = reasoning
                logger.info(
                    f"Loaded {len(timestamp_to_description)} timestamp mappings and {len(url_to_description)} URL mappings."
                )
            else:
                logger.warning(f"CSV file missing extraction_reasoning column.")
        except Exception as e:
            logger.error(f"Error reading policy descriptions from CSV: {e}")
    else:
        logger.warning(f"Policy descriptions CSV file not found: {csv_path}")

    policy_repo = PolicyRepository(session)
    existing_policies = await get_existing_policies_info(session)
    folder_pattern = re.compile(r"^(.+)_(\d{20})$")
    processed_count = 0
    skipped_count = 0
    deleted_count = 0

    for folder_name in os.listdir(scraped_policies_dir):
        folder_path = os.path.join(scraped_policies_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        match = folder_pattern.match(folder_name)
        if not match:
            logger.warning(f"Skipping folder with unexpected name format: {folder_name}")
            skipped_count += 1
            continue
        policy_title = match.group(1)
        scrape_timestamp = match.group(2)
        logger.debug(f"Checking folder: '{folder_name}' -> title='{policy_title}', timestamp={scrape_timestamp}")
        should_process = True
        if policy_title in existing_policies:
            existing_metadata = existing_policies[policy_title].get("metadata", {})
            existing_id = existing_policies[policy_title]["id"]
            deleted = False
            if existing_metadata and "scrape_timestamp" in existing_metadata:
                existing_timestamp = existing_metadata["scrape_timestamp"]
                if existing_timestamp >= scrape_timestamp:
                    logger.debug(f"Skipping older/same version: '{policy_title}'")
                    skipped_count += 1
                    should_process = False
                else:
                    logger.info(f"Newer version: '{policy_title}'. Deleting old ID {existing_id}")
                    deleted = await policy_repo.delete_by_id(existing_id)
                    deleted_count += deleted
            else:
                logger.info(f"Existing '{policy_title}' (ID: {existing_id}) lacks timestamp. Replacing.")
                deleted = await policy_repo.delete_by_id(existing_id)
                deleted_count += deleted
            if not deleted and should_process and policy_title in existing_policies:
                logger.error(f"Failed to delete old version of '{policy_title}'. Skipping update.")
                skipped_count += 1
                should_process = False
        if should_process:
            extraction_reasoning = timestamp_to_description.get(scrape_timestamp)
            if not extraction_reasoning and url_to_description:
                md_path = os.path.join(folder_path, "content.md")
                if os.path.exists(md_path):
                    try:
                        with open(md_path, "r", encoding="utf-8") as f_md:
                            markdown_content = f_md.read()
                        source_url_match = re.search(r"^# Source URL: (.*)$", markdown_content, re.MULTILINE)
                        if source_url_match:
                            source_url = source_url_match.group(1).strip()
                            extraction_reasoning = url_to_description.get(source_url)
                    except Exception as file_err:
                        logger.error(f"Error reading markdown for URL extraction: {file_err}")
            logger.debug(
                f"Description for '{policy_title}': {extraction_reasoning[:50] if extraction_reasoning else 'None'}"
            )
            await process_new_policy_folder(
                folder_path=folder_path,
                policy_title=policy_title,
                scrape_timestamp=scrape_timestamp,
                session=session,
                policy_repo=policy_repo,
                extraction_reasoning=extraction_reasoning,
            )
            processed_count += 1
    logger.info(
        f"Policy population finished. Processed/Updated: {processed_count}, Deleted old: {deleted_count}, Skipped: {skipped_count}"
    )


async def init_db(db_url: Optional[str] = None, populate: bool = True) -> None:
    """
    Initialize the database: create DB, extensions, tables, seed users, and optionally populate policies.
    """
    ensure_directories()
    db_url = db_url or str(config.DATABASE.DATABASE_URL)
    logger.info(f"Starting database initialization for: {db_url} (Populate: {populate})")

    # 1. Ensure the database itself exists
    db_exists_or_created = await create_database(db_url)
    if not db_exists_or_created:
        logger.critical(f"Failed to ensure database exists at {db_url}. Aborting initialization.")
        return

    # 2. Create engine using the potentially overridden db_url
    engine = create_async_engine(db_url, echo=config.API.DEBUG)

    try:
        # 3. Create required PostgreSQL extensions
        await create_extension(engine, "vector")

        # ******************** FIX IS HERE ********************
        # 4. Create Tables & Triggers using the engine directly (outside session transaction)
        logger.info("Creating database tables if they don't exist...")
        async with engine.begin() as conn:  # Use engine.begin() for create_all
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables checked/created.")

        logger.info("Applying search vector triggers...")
        async with engine.connect() as conn:  # Use engine.connect() for executing triggers
            for statement in create_search_vector_trigger():
                await conn.execute(text(statement))
            await conn.commit()  # Commit trigger creation
        logger.info("Search vector triggers applied.")
        # *****************************************************

        # 5. Use a session context ONLY for seeding users and populating policies
        logger.info("Seeding users and potentially populating policies...")
        async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with async_session_factory() as session:
            async with session.begin():  # Start transaction for data operations
                # 5a. Seed Users from JSON
                await seed_users_from_json(session)

                # 5b. Optionally, populate policies
                if populate:
                    logger.info("Starting policy data population from scraped_policies directory...")
                    await populate_database_from_scraped_policies(session)  # Pass the session
                else:
                    logger.info("Skipping policy data population step.")
            # Transaction committed here
            logger.info("User seeding and policy population committed.")

        logger.info("SUCCESS: Database initialization completed successfully.")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        # Rollback would have happened automatically if error was within session.begin()
    finally:
        # Always dispose the engine created specifically for this function
        if engine:
            await engine.dispose()
            logger.info("Database engine disposed.")


# (Keep drop_db function - unchanged)
async def drop_db(db_url: Optional[str] = None, force: bool = False) -> None:
    """Drops the database."""
    db_url = db_url or str(config.DATABASE.DATABASE_URL)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url_parsed = db_url.replace("postgresql+asyncpg://", "postgresql://")
    else:
        db_url_parsed = db_url
    try:
        parsed = urlparse(db_url_parsed)
        db_name = parsed.path.lstrip("/")
        if not db_name:
            logger.error("Database name could not be parsed from URL for dropping.")
            return
        admin_url = f"{parsed.scheme}://{parsed.netloc}/postgres"
        logger.warning(f"Attempting to drop database '{db_name}'... THIS WILL DELETE ALL DATA!")
        if not force:
            try:
                confirm = input(f"Are you sure you want to drop database '{db_name}'? (yes/no): ")
                if confirm.lower() != "yes":
                    logger.info("Database drop cancelled.")
                    return
            except EOFError:
                logger.warning("EOF received during confirmation. Assuming cancellation.")
                return
        conn = None
        try:
            conn = await asyncpg.connect(admin_url)
            logger.info(f"Terminating active connections to '{db_name}'...")
            await conn.execute(
                f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = $1 AND pid <> pg_backend_pid();",
                db_name,
            )
            logger.info("Connections terminated.")
            await asyncio.sleep(0.5)
            logger.info(f"Dropping database '{db_name}'...")
            await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')
            logger.info(f"SUCCESS: Database '{db_name}' dropped successfully.")
        except Exception as e:
            logger.error(f"Error dropping database '{db_name}': {e}")
        finally:
            if conn:
                await conn.close()
    except Exception as parse_err:
        logger.error(f"Error parsing database URL '{db_url}' for dropping: {parse_err}")


# (Keep main execution block - unchanged)
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize or drop the YDR Policy RAG database.")
    parser.add_argument(
        "--populate",
        action="store_true",
        help="Populate the database with new policies found in the processed data directory.",
    )
    parser.add_argument("--drop", action="store_true", help="Drop the database (USE WITH CAUTION!).")
    parser.add_argument("--db_url", help="Optional database URL to override config.")
    parser.add_argument(
        "--no-populate", action="store_true", help="Explicitly skip the population step during initialization."
    )
    parser.add_argument("--force", action="store_true", help="Force drop without confirmation (used with --drop).")

    args = parser.parse_args()
    should_populate = args.populate or (not args.drop and not args.no_populate)
    if args.drop:
        asyncio.run(drop_db(db_url=args.db_url, force=args.force))
    else:
        asyncio.run(init_db(db_url=args.db_url, populate=should_populate))
