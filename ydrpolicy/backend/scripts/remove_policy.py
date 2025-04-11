#!/usr/bin/env python
"""
Remove a policy and its associated data (chunks, images) from the database.

Can be run directly or imported and used via the `run_remove` function.

Direct Usage Examples:
    python -m ydrpolicy.backend.scripts.remove_policy --id 123
    python -m ydrpolicy.backend.scripts.remove_policy --title "Specific Policy Title"
    python -m ydrpolicy.backend.scripts.remove_policy --id 456 --force
    python -m ydrpolicy.backend.scripts.remove_policy --title "Another Title" --db_url postgresql+asyncpg://user:pass@host/dbname
"""

import os
import sys
import asyncio
import argparse
from typing import Union, Optional, Dict, Any
from pathlib import Path

# --- Add project root to sys.path ---
# This allows running the script directly using `python -m ...`
# Adjust the number of `parent` calls if your script structure is different
try:
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    # Handle case where __file__ is not defined (e.g., interactive interpreter)
    project_root = Path('.').resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


# --- Imports ---
# Need to import necessary components after path setup
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from ydrpolicy.backend.database.repository.policies import PolicyRepository
from ydrpolicy.backend.config import config as backend_config # Renamed for clarity
from ydrpolicy.backend.logger import BackendLogger # Use BackendLogger

# Initialize logger for this script
logger = BackendLogger(name="RemovePolicyScript", path=backend_config.LOGGING.FILE)


# --- Core Removal Logic ---
async def run_remove(identifier: Union[int, str], db_url: Optional[str] = None, admin_id: Optional[int] = None) -> bool:
    """
    Removes a policy and its associated data by ID or title.

    Args:
        identifier: The policy ID (int) or exact title (str).
        db_url: Optional custom database URL. If None, uses config.
        admin_id: Optional ID of the user/admin performing the action (for logging).

    Returns:
        True if the policy was successfully removed, False otherwise.
    """
    removed = False
    policy_id_for_log: Optional[int] = None
    policy_title_for_log: Optional[str] = None
    details: Dict[str, Any] = {"identifier_type": "id" if isinstance(identifier, int) else "title", "identifier_value": identifier}

    # --- Database Session Setup ---
    engine = None
    session_factory = None
    try:
        if db_url:
            logger.info(f"Using custom database URL for removal: {db_url}")
            engine = create_async_engine(db_url, echo=backend_config.API.DEBUG)
        else:
            # Import the default engine getter only if needed
            from ydrpolicy.backend.database.engine import get_async_engine
            engine = get_async_engine() # Use default engine

        session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async with session_factory() as session:
            policy_repo = PolicyRepository(session)

            # --- Find Policy and Attempt Deletion ---
            try:
                if isinstance(identifier, int):
                    policy_id_for_log = identifier
                    # Fetch policy first to get title for logging before it's deleted
                    policy = await policy_repo.get_by_id(identifier)
                    if policy:
                        policy_title_for_log = policy.title
                        details["title"] = policy_title_for_log # Add to log details
                        logger.info(f"Attempting to delete policy ID {identifier} ('{policy_title_for_log}')...")
                        
                        # Log the deletion BEFORE actually deleting the policy
                        await policy_repo.log_policy_update(
                            policy_id=policy_id_for_log,
                            admin_id=admin_id,
                            action="delete",
                            details=details
                        )
                        
                        # Now perform the actual deletion
                        removed = await policy_repo.delete_by_id(identifier)
                    else:
                        logger.error(f"Policy with ID {identifier} not found.")
                        removed = False # Ensure removed is False

                else: # identifier is title (str)
                    policy_title_for_log = identifier
                    details["title"] = policy_title_for_log
                    # Fetch policy first to get ID for logging before it's deleted
                    policy = await policy_repo.get_by_title(identifier)
                    if policy:
                        policy_id_for_log = policy.id
                        logger.info(f"Attempting to delete policy titled '{identifier}' (ID: {policy_id_for_log})...")
                        
                        # Log the deletion BEFORE actually deleting the policy
                        await policy_repo.log_policy_update(
                            policy_id=policy_id_for_log,
                            admin_id=admin_id,
                            action="delete",
                            details=details
                        )
                        
                        # Now perform the actual deletion
                        removed = await policy_repo.delete_by_title(identifier) # Calls delete_by_id internally
                    else:
                         logger.error(f"Policy with title '{identifier}' not found.")
                         removed = False # Ensure removed is False

                # --- Log Outcome only if deletion failed ---
                if not removed:
                    await policy_repo.log_policy_update(
                        policy_id=policy_id_for_log, # May be None if lookup failed
                        admin_id=admin_id,
                        action="delete_failed",
                        details=details
                    )
                
                # Commit deletion and log entry
                await session.commit()

            except Exception as e:
                logger.error(f"An error occurred during database operation: {e}", exc_info=True)
                await session.rollback() # Rollback any partial changes
                removed = False
                # We won't try to log to policy_updates after a rollback as it might fail due to FK constraints
                logger.warning(f"Policy removal failed: {e}")

    except Exception as outer_err:
         logger.error(f"An error occurred setting up database connection or session: {outer_err}", exc_info=True)
         removed = False
    finally:
        # Dispose the engine only if we created it specifically for a custom db_url
        if db_url and engine:
            await engine.dispose()
            logger.debug("Disposed custom database engine.")

    return removed


# --- Command-Line Interface Logic ---
async def main_cli():
    """Parses arguments and runs the removal process when script is called directly."""
    parser = argparse.ArgumentParser(
        description="Remove a policy and its associated data from the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python -m %(prog)s --id 123
  python -m %(prog)s --title "Specific Policy Title"
  python -m %(prog)s --id 456 --force
  python -m %(prog)s --title "Another Title" --db_url postgresql+asyncpg://user:pass@host/dbname"""
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=int, help="ID of the policy to remove.")
    group.add_argument("--title", type=str, help="Exact title of the policy to remove.")
    parser.add_argument("--db_url", help="Optional database URL to override config.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force removal without confirmation (DANGEROUS)."
    )

    args = parser.parse_args()

    identifier = args.id if args.id is not None else args.title
    id_type = "ID" if args.id is not None else "Title"

    if not args.force:
        try:
            confirm = input(f"==> WARNING <==\nAre you sure you want to remove the policy with {id_type} '{identifier}' and ALL its associated data (chunks, images)? This cannot be undone. (yes/no): ")
            if confirm.lower() != 'yes':
                logger.info("Policy removal cancelled by user.")
                return # Exit cleanly
        except EOFError:
             logger.warning("Input stream closed. Assuming cancellation.")
             return # Exit if input cannot be read (e.g., non-interactive)

    logger.warning(f"Proceeding with removal of policy {id_type}: '{identifier}'...")

    # Call the core logic function
    success = await run_remove(identifier=identifier, db_url=args.db_url, admin_id=None) # No specific admin in script context

    # Report final status
    if success:
        logger.success(f"Successfully removed policy identified by {id_type}: '{identifier}'.")
    else:
        logger.error(f"Failed to remove policy identified by {id_type}: '{identifier}'. Check logs for details.")
        sys.exit(1) # Exit with error code


# --- Main Execution Guard ---
if __name__ == "__main__":
    asyncio.run(main_cli())