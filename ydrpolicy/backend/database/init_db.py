# ydrpolicy/backend/database/init_db.py
import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import asyncpg
import pandas as pd

# Import delete statement helper
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError, NoResultFound  # Added NoResultFound
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Local Application Imports
from ydrpolicy.backend.config import config
from ydrpolicy.backend.database.engine import get_async_session
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
from ydrpolicy.data_collection.config import config as data_config
from ydrpolicy.data_collection.processors.pdf_processor import pdf_file_to_markdown
from ydrpolicy.data_collection.scrape.scraper import (
    _filter_markdown_for_txt,
    sanitize_filename,
)
import shutil

# Initialize logger
logger = logging.getLogger(__name__)


# --- create_database function remains unchanged ---
async def create_database(db_url: str) -> bool:
    """Creates the database if it doesn't exist."""
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
            result = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            if not result:
                logger.info(f"Creating database '{db_name}'...")
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"SUCCESS: Database '{db_name}' created.")
            else:
                logger.info(f"Database '{db_name}' already exists.")
            return True
        except asyncpg.exceptions.InvalidCatalogNameError:
            logger.debug(
                f"Database '{db_name}' does not exist (InvalidCatalogNameError). Will attempt creation."
            )
            if conn is None:
                try:
                    conn_admin = await asyncpg.connect(admin_url)
                    logger.info(
                        f"Re-attempting creation for '{db_name}' via admin connection..."
                    )
                    await conn_admin.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"SUCCESS: Database '{db_name}' created.")
                    await conn_admin.close()
                    return True
                except Exception as create_err:
                    logger.error(
                        f"Failed to create '{db_name}' via admin: {create_err}"
                    )
                    return False
            else:
                try:
                    logger.info(
                        f"Creating database '{db_name}' using existing admin connection..."
                    )
                    await conn.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"SUCCESS: Database '{db_name}' created.")
                    return True
                except Exception as create_err:
                    logger.error(
                        f"Failed to create '{db_name}' using existing admin: {create_err}"
                    )
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


# --- create_extension function remains unchanged ---
async def create_extension(engine: AsyncEngine, extension_name: str) -> None:
    """Creates a PostgreSQL extension if it doesn't exist."""
    logger.info(f"Ensuring extension '{extension_name}' exists...")
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"CREATE EXTENSION IF NOT EXISTS {extension_name} SCHEMA public")
            )
        logger.info(f"Extension '{extension_name}' checked/created.")
    except Exception as e:
        logger.error(f"Error creating extension '{extension_name}': {e}. Continuing...")


# --- seed_users_from_json function remains unchanged ---
async def seed_users_from_json(session: AsyncSession):
    """Reads users from users.json and creates them if they don't exist."""
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
        logger.error(
            f"User seed file '{seed_file_path}' should contain a JSON list. Skipping."
        )
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
        try:
            # Use get_by_email which should handle NoResultFound internally or raise it
            existing_user = await user_repo.get_by_email(email)
            if existing_user:
                logger.debug(f"User '{email}' already exists. Skipping.")
                skipped_count += 1
                continue
        except NoResultFound:
            logger.debug(f"User '{email}' not found, proceeding with creation.")
        except Exception as e:
            logger.error(f"Error checking for existing user '{email}': {e}. Skipping.")
            skipped_count += 1
            continue

        try:
            hashed_pw = hash_password(plain_password)
            new_user = User(
                email=email,
                full_name=full_name,
                password_hash=hashed_pw,
                is_admin=is_admin,
            )
            session.add(new_user)
            # Log preparation, actual add happens on flush/commit
            logger.info(f"Prepared new user for creation: {email} (Admin: {is_admin})")
            created_count += 1
        except Exception as e:
            logger.error(f"Error preparing user '{email}' for creation: {e}")
            skipped_count += 1  # Also count as skipped if preparation fails

    logger.info(
        f"User seeding preparation complete. Prepared: {created_count}, Skipped: {skipped_count}"
    )


# --- get_existing_policies_info function remains unchanged ---
async def get_existing_policies_info(session: AsyncSession) -> Dict[str, Dict]:
    """Fetches existing policy titles and their metadata."""
    logger.info("Fetching existing policy information from database...")
    stmt = select(Policy.id, Policy.title, Policy.policy_metadata)
    result = await session.execute(stmt)
    # Store as {title: {'id': id, 'metadata': metadata}}
    policies_info = {
        title: {"id": id, "metadata": metadata} for id, title, metadata in result
    }
    logger.info(f"Found {len(policies_info)} existing policies in database.")
    return policies_info


# --- Renamed: process_new_policy_folder -> create_new_policy ---
async def create_new_policy(
    folder_path: str,
    policy_title: str,
    scrape_timestamp: str,
    session: AsyncSession,
    extraction_reasoning: Optional[str] = None,
):
    """Creates a new policy record and its associated objects in the database."""
    logger.info(
        f"Creating new policy: '{policy_title}' from folder: {os.path.basename(folder_path)}"
    )
    md_path = os.path.join(folder_path, "content.md")
    txt_path = os.path.join(folder_path, "content.txt")

    if not os.path.exists(md_path):
        logger.error(f"  Markdown file not found: {md_path}. Skipping creation.")
        return None  # Return None to indicate failure
    if not os.path.exists(txt_path):
        logger.error(f"  Text file not found: {txt_path}. Skipping creation.")
        return None  # Return None to indicate failure

    try:
        with open(md_path, "r", encoding="utf-8") as f_md:
            markdown_content = f_md.read()
        with open(txt_path, "r", encoding="utf-8") as f_txt:
            text_content = f_txt.read()
        logger.debug(f"  Read content files for new policy '{policy_title}'.")

        source_url_match = re.search(
            r"^# Source URL: (.*)$", markdown_content, re.MULTILINE
        )
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
        logger.info(
            f"SUCCESS: Created Policy record ID: {policy.id} for title '{policy.title}'"
        )

        # --- Process images and chunks (common logic) ---
        await _process_policy_children(session, policy, folder_path, text_content)

        return policy  # Return the created policy object

    except IntegrityError as ie:
        # This could happen in a race condition if another process created it just now
        logger.error(
            f"  DB integrity error (duplicate title?) creating '{policy_title}': {ie}"
        )
        raise ie  # Reraise to ensure transaction rollback
    except Exception as e:
        logger.error(
            f"  Unexpected error creating policy '{policy_title}': {e}", exc_info=True
        )
        raise e  # Reraise to ensure transaction rollback


# --- New Function: update_existing_policy ---
async def update_existing_policy(
    existing_policy: Policy,  # Pass the fetched Policy object
    folder_path: str,
    scrape_timestamp: str,
    session: AsyncSession,
    extraction_reasoning: Optional[str] = None,
):
    """Updates an existing policy record and its associated objects."""
    policy_title = existing_policy.title  # Get title from existing object
    policy_id = existing_policy.id
    logger.info(
        f"Updating existing policy: '{policy_title}' (ID: {policy_id}) from folder: {os.path.basename(folder_path)}"
    )
    md_path = os.path.join(folder_path, "content.md")
    txt_path = os.path.join(folder_path, "content.txt")

    if not os.path.exists(md_path):
        logger.error(
            f"  Markdown file not found: {md_path}. Skipping update for policy ID {policy_id}."
        )
        return False  # Indicate failure
    if not os.path.exists(txt_path):
        logger.error(
            f"  Text file not found: {txt_path}. Skipping update for policy ID {policy_id}."
        )
        return False  # Indicate failure

    try:
        with open(md_path, "r", encoding="utf-8") as f_md:
            markdown_content = f_md.read()
        with open(txt_path, "r", encoding="utf-8") as f_txt:
            text_content = f_txt.read()
        logger.debug(f"  Read content files for updating policy ID {policy_id}.")

        source_url_match = re.search(
            r"^# Source URL: (.*)$", markdown_content, re.MULTILINE
        )
        source_url = source_url_match.group(1).strip() if source_url_match else None

        # --- Delete existing children (Images, Chunks) ---
        logger.debug(f"  Deleting existing images for policy ID {policy_id}...")
        await session.execute(delete(Image).where(Image.policy_id == policy_id))
        logger.debug(f"  Deleting existing chunks for policy ID {policy_id}...")
        await session.execute(
            delete(PolicyChunk).where(PolicyChunk.policy_id == policy_id)
        )
        # Flush deletions before adding new children to avoid potential conflicts if IDs were reused somehow
        # Although usually not strictly necessary if PKs are sequences. Doesn't hurt.
        await session.flush()
        logger.debug(f"  Flushed deletion of children for policy ID {policy_id}.")

        # --- Update Policy attributes ---
        existing_policy.source_url = source_url
        existing_policy.markdown_content = markdown_content
        existing_policy.text_content = text_content
        existing_policy.description = extraction_reasoning
        # Update metadata - merge or replace as needed. Replacing seems appropriate here.
        existing_policy.policy_metadata = {
            "scrape_timestamp": scrape_timestamp,
            "source_folder": os.path.basename(folder_path),
            "processed_at": datetime.utcnow().isoformat(),
            # Add previous timestamp if needed: "previous_scrape_timestamp": existing_policy.policy_metadata.get("scrape_timestamp"),
        }
        # updated_at should be handled automatically by the model's default/onupdate

        # Mark the existing policy as modified (SQLAlchemy often detects changes automatically, but explicit add doesn't hurt)
        session.add(existing_policy)

        # --- Re-process images and chunks with new content ---
        await _process_policy_children(
            session, existing_policy, folder_path, text_content
        )

        logger.info(
            f"SUCCESS: Updated Policy record ID: {policy_id} for title '{policy_title}'"
        )
        return True  # Indicate success

    except Exception as e:
        logger.error(
            f"  Unexpected error updating policy '{policy_title}' (ID: {policy_id}): {e}",
            exc_info=True,
        )
        # Let the exception propagate to roll back the transaction
        raise e


# --- Helper Function: _process_policy_children (Extracted common logic) ---
async def _process_policy_children(
    session: AsyncSession, policy: Policy, folder_path: str, text_content: str
):
    """Processes and adds Images and PolicyChunks for a given policy."""
    policy_id = policy.id
    policy_title = policy.title

    # Process images
    image_files = [
        f
        for f in os.listdir(folder_path)
        if f.lower().startswith("img-")
        and f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
    ]
    image_count = 0
    for img_filename in image_files:
        try:
            session.add(
                Image(
                    policy_id=policy_id,
                    filename=img_filename,
                    relative_path=img_filename,
                )
            )
            image_count += 1
        except Exception as img_err:
            logger.error(
                f"  Error creating Image object for '{img_filename}' in policy '{policy_title}' (ID: {policy_id}): {img_err}"
            )
    if image_count > 0:
        # Flush image additions before chunking? Not strictly necessary.
        # await session.flush()
        logger.info(
            f"  Prepared {image_count} Image records for policy ID {policy_id}."
        )

    # Process chunks and embeddings
    chunks = chunk_text(
        text=text_content,
        chunk_size=config.RAG.CHUNK_SIZE,
        chunk_overlap=config.RAG.CHUNK_OVERLAP,
    )
    logger.info(f"  Split text into {len(chunks)} chunks for policy ID {policy_id}.")

    if not chunks:
        logger.warning(f"  No chunks generated for '{policy_title}' (ID: {policy_id}).")
        return  # Nothing more to do if no chunks

    try:
        embeddings = await embed_texts(chunks)
        if len(embeddings) != len(chunks):
            logger.error(
                f"  Embedding count ({len(embeddings)}) does not match chunk count ({len(chunks)}) for policy '{policy_title}' (ID: {policy_id}). Aborting chunk processing for this policy."
            )
            return  # Stop processing chunks for this policy if counts mismatch
        logger.info(
            f"  Generated {len(embeddings)} embeddings for policy ID {policy_id}."
        )
    except Exception as emb_err:
        logger.error(
            f"  Embedding failed for '{policy_title}' (ID: {policy_id}): {emb_err}.",
            exc_info=True,
        )
        return  # Stop processing chunks for this policy if embedding fails

    # Add PolicyChunk objects
    chunk_count = 0
    for i, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
        try:
            embedding_list = (
                embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
            )
            session.add(
                PolicyChunk(
                    policy_id=policy_id,
                    chunk_index=i,
                    content=chunk_content,
                    embedding=embedding_list,
                )
            )
            chunk_count += 1
        except Exception as chunk_err:
            logger.error(
                f"  Error creating PolicyChunk index {i} for policy ID {policy_id}: {chunk_err}"
            )
            # Decide if one chunk error should stop adding others
    if chunk_count > 0:
        # await session.flush() # Flush only if necessary before next step
        logger.info(
            f"  Prepared {chunk_count} PolicyChunk records for policy ID {policy_id}."
        )


# --- populate_database_from_scraped_policies (Modified to use create/update) ---
async def populate_database_from_scraped_policies(session: AsyncSession):
    """
    Scans the scraped policies directory, identifies new/updated policies,
    and populates the database within the given session using create or update logic.
    """
    scraped_policies_dir = config.PATHS.SCRAPED_POLICIES_DIR
    if not os.path.isdir(scraped_policies_dir):
        logger.error(f"Scraped policies directory not found: {scraped_policies_dir}")
        return

    logger.info(f"Scanning scraped policies directory: {scraped_policies_dir}")

    # --- Load descriptions (unchanged) ---
    timestamp_to_description: Dict[str, str] = {}
    url_to_description: Dict[str, str] = {}
    csv_path = os.path.join(
        config.PATHS.PROCESSED_DATA_DIR, "processed_policies_log.csv"
    )
    if os.path.exists(csv_path):
        try:
            policy_df = pd.read_csv(csv_path)
            logger.info(f"Reading policy descriptions from CSV: {csv_path}")
            timestamp_mapping = "timestamp" in policy_df.columns
            url_mapping = "url" in policy_df.columns
            if "extraction_reasoning" in policy_df.columns:
                for _, row in policy_df.iterrows():
                    if pd.notna(row["extraction_reasoning"]):
                        reasoning = str(row["extraction_reasoning"])
                        if timestamp_mapping and pd.notna(row["timestamp"]):
                            timestamp_to_description[str(row["timestamp"])] = reasoning
                        if url_mapping and pd.notna(row["url"]):
                            url_to_description[str(row["url"])] = reasoning
                logger.info(
                    f"Loaded {len(timestamp_to_description)} timestamp mappings and {len(url_to_description)} URL mappings for descriptions."
                )
            else:
                logger.warning(
                    f"CSV file '{csv_path}' missing 'extraction_reasoning' column."
                )
        except Exception as e:
            logger.error(
                f"Error reading policy descriptions from CSV '{csv_path}': {e}"
            )
    else:
        logger.warning(f"Policy descriptions CSV file not found: {csv_path}")

    # --- Get existing policies and initialize counters ---
    policy_repo = PolicyRepository(session)  # Still useful for fetching by ID
    existing_policies = await get_existing_policies_info(
        session
    )  # {title: {'id': id, 'metadata': meta}}
    folder_pattern = re.compile(r"^(.+)_(\d{20})$")

    processed_new_count = 0
    processed_update_count = 0
    skipped_count = 0
    error_count = 0
    # Keep track of titles processed in this run to handle multiple folders for the same title
    processed_titles_in_run: Set[str] = set()

    # --- Iterate through folders ---
    for folder_name in sorted(os.listdir(scraped_policies_dir)):
        folder_path = os.path.join(scraped_policies_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue

        match = folder_pattern.match(folder_name)
        if not match:
            logger.warning(
                f"Skipping folder with unexpected name format: {folder_name}"
            )
            skipped_count += 1
            continue

        policy_title = match.group(1)
        scrape_timestamp = match.group(2)
        logger.debug(
            f"Checking folder: '{folder_name}' -> title='{policy_title}', timestamp={scrape_timestamp}"
        )

        # --- Check if already processed this title in this run ---
        if policy_title in processed_titles_in_run:
            logger.warning(
                f"Policy title '{policy_title}' was already processed or updated in this run from another folder. Skipping redundant processing for folder '{folder_name}'."
            )
            skipped_count += 1
            continue

        existing_policy_info = existing_policies.get(policy_title)
        should_process = False
        is_update = False  # Flag to differentiate create vs update

        if existing_policy_info:
            # Policy title exists in DB
            existing_id = existing_policy_info["id"]
            existing_metadata = existing_policy_info.get("metadata", {})

            if existing_metadata and "scrape_timestamp" in existing_metadata:
                existing_timestamp = existing_metadata["scrape_timestamp"]
                try:
                    if scrape_timestamp > existing_timestamp:
                        logger.info(
                            f"Newer version found for '{policy_title}'. Scraped: {scrape_timestamp}, Existing DB: {existing_timestamp}. Will update existing ID {existing_id}."
                        )
                        should_process = True
                        is_update = True
                    else:
                        logger.debug(
                            f"Skipping older/same version for '{policy_title}': Folder timestamp '{scrape_timestamp}' <= DB timestamp '{existing_timestamp}'."
                        )
                        skipped_count += 1
                        # Add to processed set even if skipped to prevent other folders triggering updates mistakenly
                        processed_titles_in_run.add(policy_title)
                except TypeError as te:
                    logger.error(
                        f"Timestamp comparison error for '{policy_title}' (Folder: {scrape_timestamp}, DB: {existing_timestamp}): {te}. Assuming update needed."
                    )
                    should_process = True
                    is_update = True
            else:
                logger.info(
                    f"Existing '{policy_title}' (ID: {existing_id}) lacks timestamp or metadata. Assuming update needed."
                )
                should_process = True
                is_update = True
        else:
            # Policy title does not exist in DB - it's new
            logger.info(
                f"New policy found: '{policy_title}' from folder '{folder_name}'. Will create."
            )
            should_process = True
            is_update = False

        # --- Process (Create or Update) ---
        if should_process:
            # --- Get description (unchanged logic) ---
            extraction_reasoning = timestamp_to_description.get(scrape_timestamp)
            if not extraction_reasoning and url_to_description:
                md_path_for_url = os.path.join(folder_path, "content.md")
                if os.path.exists(md_path_for_url):
                    try:
                        with open(md_path_for_url, "r", encoding="utf-8") as f_md_url:
                            md_content_for_url = f_md_url.read()
                        source_url_match_desc = re.search(
                            r"^# Source URL: (.*)$", md_content_for_url, re.MULTILINE
                        )
                        if source_url_match_desc:
                            source_url_desc = source_url_match_desc.group(1).strip()
                            extraction_reasoning = url_to_description.get(
                                source_url_desc
                            )
                            if extraction_reasoning:
                                logger.debug(
                                    f"Found description for '{policy_title}' via URL match: {source_url_desc}"
                                )
                    except Exception as file_err:
                        logger.error(
                            f"Error reading markdown for URL-based description extraction for '{policy_title}': {file_err}"
                        )
            logger.debug(
                f"Description for '{policy_title}' (timestamp: {scrape_timestamp}): '{extraction_reasoning[:50] if extraction_reasoning else 'None'}...'"
            )

            # --- Call appropriate function ---
            try:
                if is_update:
                    # Fetch the actual Policy object to update
                    try:
                        policy_to_update = await policy_repo.get_by_id(existing_id)
                        if policy_to_update:
                            update_success = await update_existing_policy(
                                existing_policy=policy_to_update,
                                folder_path=folder_path,
                                scrape_timestamp=scrape_timestamp,
                                session=session,
                                extraction_reasoning=extraction_reasoning,
                            )
                            if update_success:
                                processed_update_count += 1
                                processed_titles_in_run.add(policy_title)
                            else:
                                error_count += 1
                                # Don't add to processed_titles_in_run if update failed internally
                        else:
                            # Should not happen if existing_policy_info was found, but handle defensively
                            logger.error(
                                f"Could not find policy with ID {existing_id} for update, despite initial check finding title '{policy_title}'. Skipping update."
                            )
                            error_count += 1

                    except NoResultFound:
                        logger.error(
                            f"Policy with ID {existing_id} (title: '{policy_title}') not found during update attempt. Skipping."
                        )
                        error_count += 1
                    except Exception as fetch_err:
                        logger.error(
                            f"Error fetching policy ID {existing_id} for update: {fetch_err}. Skipping update.",
                            exc_info=True,
                        )
                        error_count += 1

                else:  # is_create
                    created_policy = await create_new_policy(
                        folder_path=folder_path,
                        policy_title=policy_title,
                        scrape_timestamp=scrape_timestamp,
                        session=session,
                        extraction_reasoning=extraction_reasoning,
                    )
                    if created_policy:
                        processed_new_count += 1
                        processed_titles_in_run.add(policy_title)
                    else:
                        error_count += 1
                        # Don't add to processed_titles_in_run if create failed internally

            except IntegrityError as ie:
                # Catch potential integrity errors specifically during create/update calls
                logger.error(
                    f"DATABASE INTEGRITY ERROR processing '{policy_title}' from '{folder_name}': {ie}. This policy might already exist due to a race condition or inconsistent state. Skipping.",
                    exc_info=False,
                )
                error_count += 1
                processed_titles_in_run.add(
                    policy_title
                )  # Mark as handled to prevent retries
            except Exception as proc_err:
                # Catch any other unexpected errors during create/update
                logger.error(
                    f"UNEXPECTED ERROR processing '{policy_title}' from '{folder_name}': {proc_err}. Skipping.",
                    exc_info=True,
                )
                error_count += 1
                processed_titles_in_run.add(policy_title)  # Mark as handled

    # --- Final Log ---
    logger.info(
        f"Policy population finished. Created New: {processed_new_count}, Updated Existing: {processed_update_count}, "
        f"Skipped (older/duplicate/format): {skipped_count}, Errors during processing: {error_count}"
    )


# --- New: Populate database from local PDFs ---
def _find_latest_policies_dir(base_dir: str) -> Optional[str]:
    """Find the latest 'policies_YYYYMMDD' directory under base_dir."""
    if not os.path.isdir(base_dir):
        logger.error(f"Source policies base directory not found: {base_dir}")
        return None
    latest_dir: Optional[str] = None
    latest_key: Optional[int] = None
    pattern = re.compile(r"^policies_(\d{8})$")
    for name in os.listdir(base_dir):
        full = os.path.join(base_dir, name)
        if not os.path.isdir(full):
            continue
        m = pattern.match(name)
        if not m:
            continue
        try:
            key = int(m.group(1))
        except ValueError:
            continue
        if latest_key is None or key > latest_key:
            latest_key = key
            latest_dir = full
    return latest_dir


def _prettify_title_from_filename(name: str) -> str:
    """Create a human-readable title from a filename stem."""
    base = os.path.splitext(os.path.basename(name))[0]
    pretty = re.sub(r"[_\-]+", " ", base).strip()
    pretty = re.sub(r"\s+", " ", pretty)
    return pretty or base


# Note: OCR-based local PDF conversion handled via pdf_file_to_markdown


async def populate_database_from_local_pdfs(
    session: AsyncSession,
    source_policies_root: Optional[str] = None,
    global_download_url: Optional[str] = None,
) -> None:
    """
    Scan latest local policies directory and ingest PDFs as policies.

    - Finds latest directory under config.PATHS.SOURCE_POLICIES_DIR matching 'policies_YYYYMMDD'
    - Recursively scans for .pdf files
    - For each PDF, extracts text with PyPDF
    - Writes a structured folder under SCRAPED_POLICIES_DIR as '<title>_<timestamp>' with content.md and content.txt
    - Reuses create/update logic to insert into DB and generate chunks/embeddings
    """
    base_dir = config.PATHS.SOURCE_POLICIES_DIR
    root_dir = (
        source_policies_root
        if source_policies_root
        else _find_latest_policies_dir(base_dir)
    )
    if not root_dir or not os.path.isdir(root_dir):
        logger.error(f"Local policies directory not found or invalid: {root_dir}")
        return

    logger.info(f"Scanning local PDFs under: {root_dir}")
    local_policies_dir = config.PATHS.LOCAL_POLICIES_DIR
    os.makedirs(local_policies_dir, exist_ok=True)

    # Load existing policies for update decisions
    existing_policies = await get_existing_policies_info(session)

    created_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0
    # Prepare CSV log path (append mode)
    csv_log_path = os.path.join(
        config.PATHS.PROCESSED_DATA_DIR, "processed_policies_log.csv"
    )
    csv_header = (
        "url,file_path,include,found_links_count,definite_links,probable_links,timestamp,"
        "contains_policy,policy_title,policy_content_path,extraction_reasoning\n"
    )
    if not os.path.exists(csv_log_path):
        try:
            with open(csv_log_path, "w", encoding="utf-8") as f:
                f.write(csv_header)
        except Exception as e:
            logger.warning(f"Could not create CSV log at {csv_log_path}: {e}")

    # Walk recursively for PDFs
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if not filename.lower().endswith(".pdf"):
                continue
            pdf_path = os.path.join(dirpath, filename)
            # Use filename to generate a human-readable title; folder-safe via sanitize_filename
            title_pretty = _prettify_title_from_filename(filename)

            # Check existing policy timestamp to decide create/update/skip
            existing_info = existing_policies.get(title_pretty)
            is_update = False
            if existing_info:
                existing_meta = existing_info.get("metadata", {}) or {}
                existing_ts = existing_meta.get("scrape_timestamp")
                # We will compare after we determine OCR timestamp

            # Convert local PDF to markdown via OCR (shared with crawler)
            md_output_dir = data_config.PATHS.MARKDOWN_DIR
            os.makedirs(md_output_dir, exist_ok=True)
            md_path, raw_timestamp = pdf_file_to_markdown(
                pdf_path, md_output_dir, data_config
            )
            if not md_path or not os.path.exists(md_path) or not raw_timestamp:
                logger.warning(
                    f"OCR/Markdown conversion failed for PDF. Skipping: {pdf_path}"
                )
                skipped_count += 1
                continue

            # Determine timestamp for folder naming and metadata
            scrape_timestamp = raw_timestamp
            # Now that we have ts, decide update vs skip
            if existing_info:
                existing_meta = existing_info.get("metadata", {}) or {}
                existing_ts = existing_meta.get("scrape_timestamp")
                if isinstance(existing_ts, str) and scrape_timestamp <= existing_ts:
                    skipped_count += 1
                    logger.debug(
                        f"Skipping '{title_pretty}' (OCR ts {scrape_timestamp} <= existing {existing_ts})."
                    )
                    continue
                else:
                    is_update = True

            # Read markdown and produce text via scraper helper
            try:
                with open(md_path, "r", encoding="utf-8") as f_md:
                    raw_md_content = f_md.readlines()
                text_content = _filter_markdown_for_txt(raw_md_content)
                # Prepend header to markdown to include source URL and provenance
                header_lines = [
                    f"# Source URL: {global_download_url or ''}",
                    f"# Imported From: Local PDF",
                    f"# Original File: {filename}",
                    f"# Timestamp: {scrape_timestamp}",
                    "\n---\n\n",
                ]
                markdown_content = "".join(header_lines) + "".join(raw_md_content)
            except Exception as e:
                logger.error(f"Failed to prepare markdown/text for '{pdf_path}': {e}")
                error_count += 1
                continue

            # Write structured folder in local_policies_dir to reuse existing logic
            folder_name = f"{sanitize_filename(title_pretty)}_{scrape_timestamp}"
            dest_folder = os.path.join(local_policies_dir, folder_name)
            try:
                os.makedirs(dest_folder, exist_ok=True)
                md_path = os.path.join(dest_folder, "content.md")
                txt_path = os.path.join(dest_folder, "content.txt")
                with open(md_path, "w", encoding="utf-8") as f_md_out:
                    f_md_out.write(markdown_content)
                with open(txt_path, "w", encoding="utf-8") as f_txt:
                    f_txt.write(text_content)
                # Copy images from OCR output directory if present
                source_img_dir = os.path.join(md_output_dir, scrape_timestamp)
                if os.path.isdir(source_img_dir):
                    copied = 0
                    for item in os.listdir(source_img_dir):
                        s = os.path.join(source_img_dir, item)
                        d = os.path.join(dest_folder, item)
                        if os.path.isfile(s):
                            try:
                                shutil.copy2(s, d)
                                copied += 1
                            except Exception as img_err:
                                logger.warning(
                                    f"Failed to copy image '{item}' for '{title_pretty}': {img_err}"
                                )
                    if copied:
                        logger.info(
                            f"Copied {copied} image(s) to '{dest_folder}' for '{title_pretty}'."
                        )
            except Exception as e:
                logger.error(
                    f"Failed to write structured files for '{title_pretty}': {e}"
                )
                error_count += 1
                continue

            # Create or update using existing functions
            try:
                if is_update and existing_info:
                    policy_id = existing_info["id"]
                    policy_obj = await PolicyRepository(session).get_by_id(policy_id)
                    if policy_obj is None:
                        logger.warning(
                            f"Expected existing policy ID {policy_id} for '{title_pretty}' not found. Creating new."
                        )
                        created = await create_new_policy(
                            folder_path=dest_folder,
                            policy_title=title_pretty,
                            scrape_timestamp=scrape_timestamp,
                            session=session,
                            extraction_reasoning="Imported from local PDFs",
                        )
                        if created:
                            created_count += 1
                            existing_policies[title_pretty] = {
                                "id": created.id,
                                "metadata": created.policy_metadata,
                            }
                    else:
                        ok = await update_existing_policy(
                            existing_policy=policy_obj,
                            folder_path=dest_folder,
                            scrape_timestamp=scrape_timestamp,
                            session=session,
                            extraction_reasoning="Imported from local PDFs (updated)",
                        )
                        if ok:
                            updated_count += 1
                            # update local map
                            existing_policies[title_pretty] = {
                                "id": policy_obj.id,
                                "metadata": {"scrape_timestamp": scrape_timestamp},
                            }
                else:
                    created = await create_new_policy(
                        folder_path=dest_folder,
                        policy_title=title_pretty,
                        scrape_timestamp=scrape_timestamp,
                        session=session,
                        extraction_reasoning="Imported from local PDFs",
                    )
                    if created:
                        created_count += 1
                        existing_policies[title_pretty] = {
                            "id": created.id,
                            "metadata": created.policy_metadata,
                        }
            except Exception as e:
                logger.error(
                    f"Failed to create/update policy for '{title_pretty}': {e}"
                )
                error_count += 1

            # Append a row to CSV log to record this processed local policy
            try:
                # Compose CSV fields similar to scraped flow
                url_field = (global_download_url or "").strip()
                file_basename = os.path.basename(md_path)
                include = True
                found_links_count = 0
                definite_links = "[]"
                probable_links = "[]"
                timestamp_field = scrape_timestamp
                contains_policy = True
                policy_title_field = title_pretty
                policy_content_path = os.path.join(dest_folder, "content.md")
                reasoning_field = "Imported from local PDFs"
                row = f'{url_field},{file_basename},{str(include)},{found_links_count},"{definite_links}","{probable_links}",{timestamp_field},{str(contains_policy)},{policy_title_field},{policy_content_path},{reasoning_field}\n'
                with open(csv_log_path, "a", encoding="utf-8") as f:
                    f.write(row)
            except Exception as log_err:
                logger.warning(
                    f"Failed to append to processed_policies_log.csv: {log_err}"
                )

    logger.info(
        f"Local PDF ingestion finished. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count}"
    )


async def ingest_policies_from_local_pdfs(
    db_url: Optional[str] = None,
    source_policies_root: Optional[str] = None,
    global_download_url: Optional[str] = None,
) -> None:
    """Entry point helper: open engine/session and ingest local PDFs into the DB."""
    ensure_directories()
    effective_db_url = db_url or str(config.DATABASE.DATABASE_URL)
    engine = create_async_engine(effective_db_url, echo=config.API.DEBUG)
    try:
        async_session_factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with async_session_factory() as session:
            async with session.begin():
                await populate_database_from_local_pdfs(
                    session=session,
                    source_policies_root=source_policies_root,
                    global_download_url=global_download_url,
                )
    finally:
        await engine.dispose()


# --- init_db function remains largely unchanged, calls populate... ---
async def init_db(db_url: Optional[str] = None, populate: bool = True) -> None:
    """
    Initialize the database: create DB, extensions, tables, seed users, and optionally populate policies.
    """
    ensure_directories()
    db_url = db_url or str(config.DATABASE.DATABASE_URL)
    logger.info(
        f"Starting database initialization for: {db_url} (Populate: {populate})"
    )

    db_exists_or_created = await create_database(db_url)
    if not db_exists_or_created:
        logger.critical(
            f"Failed to ensure database exists at {db_url}. Aborting initialization."
        )
        return

    engine = create_async_engine(db_url, echo=config.API.DEBUG)

    try:
        await create_extension(engine, "vector")

        logger.info("Creating database tables if they don't exist...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables checked/created.")

        logger.info("Applying search vector triggers...")
        async with engine.connect() as conn:
            trigger_statements = create_search_vector_trigger()
            if trigger_statements:
                for statement in trigger_statements:
                    await conn.execute(text(statement))
                await conn.commit()
                logger.info("Search vector triggers applied.")
            else:
                logger.info("No search vector triggers defined to apply.")

        logger.info("Beginning data seeding and population phase...")
        async_session_factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )

        async with async_session_factory() as session:
            async with session.begin():  # Start a single transaction for all data operations
                logger.info("Transaction started for data operations.")
                await seed_users_from_json(session)

                if populate:
                    logger.info(
                        "Starting policy data population from scraped_policies directory..."
                    )
                    await populate_database_from_scraped_policies(
                        session
                    )  # Calls the updated function
                else:
                    logger.info(
                        "Skipping policy data population step as per configuration."
                    )

            logger.info("Data operations transaction committed successfully.")

        logger.info("SUCCESS: Database initialization completed successfully.")

    except Exception as e:
        logger.error(
            f"Database initialization failed during table/data setup: {e}",
            exc_info=True,
        )
        # Rollback happens automatically via 'async with session.begin():' context manager
    finally:
        if engine:
            await engine.dispose()
            logger.info("Database engine disposed.")


# --- drop_db function remains unchanged ---
async def drop_db(db_url: Optional[str] = None, force: bool = False) -> None:
    """Drops the specified database. USE WITH EXTREME CAUTION."""
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
        logger.warning(
            f"Attempting to drop database '{db_name}' at host '{parsed.hostname}'... THIS WILL DELETE ALL DATA!"
        )

        if not force:
            try:
                confirm = input(
                    f"Are you ABSOLUTELY SURE you want to drop database '{db_name}'? This cannot be undone. (Type 'yes' to confirm): "
                )
                if confirm.lower() != "yes":
                    logger.info("Database drop cancelled by user.")
                    return
            except EOFError:
                logger.warning(
                    "EOF received during confirmation prompt. Assuming cancellation."
                )
                return

        conn = None
        try:
            conn = await asyncpg.connect(admin_url)
            logger.info(
                f"Terminating any active connections to database '{db_name}'..."
            )
            terminate_query = """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = $1
              AND pid <> pg_backend_pid();
            """
            await conn.execute(terminate_query, db_name)
            logger.info(f"Connections terminated for '{db_name}'.")
            await asyncio.sleep(0.5)
            logger.info(f"Executing DROP DATABASE command for '{db_name}'...")
            await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')
            logger.info(f"SUCCESS: Database '{db_name}' dropped successfully.")
        except Exception as e:
            logger.error(
                f"Error encountered while dropping database '{db_name}': {e}",
                exc_info=True,
            )
        finally:
            if conn:
                await conn.close()
                logger.debug("Admin connection for dropping database closed.")
    except Exception as parse_err:
        logger.error(f"Error parsing database URL '{db_url}' for dropping: {parse_err}")


# --- Main execution block remains unchanged ---
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Initialize or drop the YDR Policy RAG database."
    )
    parser.add_argument(
        "--populate",
        action="store_true",
        help="Populate the database with new policies found in the scraped policies directory during initialization.",
    )
    parser.add_argument(
        "--no-populate",
        action="store_true",
        help="Explicitly skip the policy population step during initialization (default is to populate unless --drop is specified).",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop the database instead of initializing (USE WITH CAUTION!).",
    )
    parser.add_argument(
        "--db_url",
        type=str,
        default=None,
        help="Optional database URL (e.g., 'postgresql+asyncpg://user:pass@host:port/dbname') to override the one in config.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force drop without confirmation prompt (only applies if --drop is specified).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose (DEBUG) logging."
    )

    args = parser.parse_args()

    if args.verbose:
        # Set root logger level first
        logging.getLogger().setLevel(logging.DEBUG)
        # Then set specific loggers if needed (or let them inherit)
        logging.getLogger("ydrpolicy").setLevel(logging.DEBUG)
        logging.getLogger("sqlalchemy.engine").setLevel(
            logging.INFO
        )  # Or DEBUG for very verbose SQL
        logger.setLevel(logging.DEBUG)  # Ensure our own logger is DEBUG
        logger.info("Verbose logging enabled.")

    should_populate = args.populate or (not args.drop and not args.no_populate)

    effective_db_url = args.db_url or str(config.DATABASE.DATABASE_URL)  # Define once

    if args.drop:
        logger.info(f"Initiating database drop procedure for URL: {effective_db_url}")
        asyncio.run(drop_db(db_url=effective_db_url, force=args.force))
    else:
        logger.info(
            f"Initiating database initialization procedure for URL: {effective_db_url}"
        )
        asyncio.run(init_db(db_url=effective_db_url, populate=should_populate))

    logger.info("Database command finished.")
