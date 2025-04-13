#!/usr/bin/env python
# main.py
"""
Main entry point for the YDR Policy RAG Application Engine.

Provides Command-Line Interface (CLI) commands for various operational modes:
- database: Manage database schema (creation, deletion) and data population.
- policy:   Run the data collection pipeline (crawling, scraping, processing).
- mcp:      Start the Model Context Protocol (MCP) server to provide tools.
- agent:    Run the chat agent via API (with persistent history) or in a basic
            terminal mode (with temporary session history).
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from agents import Agent
from agents.tracing import set_tracing_disabled  # Import the function
import typer
import uvicorn  # Needed for running FastAPI app in agent command
import logging  # Import standard logging module

# --- Add project root to sys.path ---
# This ensures that modules within the 'ydrpolicy' package can be imported
# correctly when this script is run from the project root directory.
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    # Fallback for environments where __file__ might not be defined (e.g., interactive)
    project_root = Path(".").resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# --- Typer App Definition ---
# Initialize the Typer application which provides the CLI framework.
app = typer.Typer(
    name="ydrpolicy",
    help="Yale Radiology Policies RAG Application Engine CLI",
    add_completion=False,  # Disable shell completion for simplicity
    rich_markup_mode="markdown",  # Allow Markdown in help strings
)


# --- Main App Callback ---
# This function runs *before* any specific command is executed.
# It's used here to process global flags like --no-log and --log-level,
# and to perform the centralized logging setup.
@app.callback(invoke_without_command=True)  # Ensure callback runs even if no command is given
def main_callback(
    ctx: typer.Context,  # The Typer context object, used to pass data to commands
    no_log: bool = typer.Option(
        False,
        "--no-log",
        help="Disable ALL logging (console and file). Overrides other log settings.",
        is_eager=True,  # Process this argument before others, essential for disabling logs early
    ),
    log_level: Optional[str] = typer.Option(
        None,
        "--log-level",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR). Overrides config.",
        case_sensitive=False,  # Allow lowercase level names
    ),
    trace: bool = typer.Option(False, "--trace", help="Enable OpenAI trace uploading."),  # Add new flag
):
    """
    Main entry point callback. Initializes logging configuration based on flags.
    Stores configuration objects in the Typer context for commands to access.
    """
    # Import configurations dynamically here. Ensures they are loaded after
    # environment variables might have been set or sourced.
    try:
        from ydrpolicy.backend.config import config as backend_config
        from ydrpolicy.data_collection.config import config as data_config
    except ImportError as e:
        print(f"ERROR: Failed to import configuration modules: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

    # Import the centralized logging setup function.
    try:
        from ydrpolicy.logging_setup import setup_logging
    except ImportError as e:
        print(f"ERROR: Failed to import logging setup module: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

    # Store configurations in the context meta dictionary for commands to retrieve.
    ctx.meta["backend_config"] = backend_config
    ctx.meta["data_config"] = data_config
    # Store the disable flag status for potential checks within commands (e.g., for stdio).
    ctx.meta["log_disabled"] = no_log

    # Determine effective logging settings based on CLI flags and config defaults.
    # CLI flags (--log-level, --no-log) take precedence.
    effective_log_level = log_level  # Use CLI override if provided
    log_disabled_flag = no_log

    # Handle OpenAI tracing flag
    if trace:
        print("NOTICE: OpenAI trace uploading enabled via --trace flag.", file=sys.stderr)
    else:
        print("NOTICE: OpenAI trace uploading disabled by default.", file=sys.stderr)
        set_tracing_disabled(True)

    # Call the centralized setup function to configure Python's standard logging system.
    setup_logging(
        log_level_str=effective_log_level,  # Pass level override or None (setup uses config default)
        disable_logging=log_disabled_flag,
        log_to_console=not log_disabled_flag,  # Console logging is ON unless explicitly disabled
        # File paths are read directly from the imported configs inside setup_logging
    )

    # Check if a command was actually invoked by the user.
    # If not (e.g., user just ran `uv run main.py`), optionally print help.
    if ctx.invoked_subcommand is None and not ctx.params.get("help"):  # Check if built-in help was triggered
        print("No command specified. Use --help to see available commands.")
        # raise typer.Exit() # Optionally exit if no command given


# --- Database Command ---
@app.command(name="database")
def db_command(
    # Typer context is passed automatically
    ctx: typer.Context,
    # Command-specific options
    init: bool = typer.Option(False, "--init", help="Initialize the database (create tables, extensions)."),
    populate: bool = typer.Option(
        False,
        "--populate",
        help="Populate the database from processed policies (implies --init).",
    ),
    drop: bool = typer.Option(False, "--drop", help="Drop the database (DANGEROUS!)."),
    force: bool = typer.Option(False, "--force", help="Force drop without confirmation."),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Optional database URL override."),
):
    """
    Manage the application database schema and data.

    - Use `--init` to create tables and extensions if they don't exist.
    - Use `--populate` to **initialize AND populate** the database with policies from the scraped data directory. This is the most common command for setup.
    - Use `--drop --force` to **completely remove** the database (requires confirmation unless `--force` is used).
    """
    # Get the standard logger instance for this part of the application.
    # Configuration (handlers, level) was done in the main_callback.
    logger = logging.getLogger("ydrpolicy.backend.database")
    # Retrieve the backend config object stored in the context by the callback.
    backend_config = ctx.meta["backend_config"]

    # Import the database management module *only when this command is run*.
    try:
        from ydrpolicy.backend.database import init_db as db_manager
    except ImportError as e:
        logger.error(f"Failed to import database module: {e}. Ensure backend components are installed.")
        raise typer.Exit(code=1)

    logger.info("Executing database command...")  # Logged only if logging is enabled and level is INFO/DEBUG.
    # Determine the target database URL (CLI override or config default).
    target_db_url = db_url or str(backend_config.DATABASE.DATABASE_URL)

    # Execute the requested database operation using asyncio.run for async functions.
    if drop:
        logger.warning(f"Database drop requested for URL: {target_db_url}")
        asyncio.run(db_manager.drop_db(db_url=target_db_url, force=force))
    elif populate:
        logger.info(f"Database initialization and population requested for URL: {target_db_url}")
        asyncio.run(db_manager.init_db(db_url=target_db_url, populate=True))
    elif init:
        logger.info(f"Database initialization (no population) requested for URL: {target_db_url}")
        asyncio.run(db_manager.init_db(db_url=target_db_url, populate=False))
    else:
        # If no valid action specified for this command, print help and exit.
        logger.info("No database action specified. Use --init, --populate, or --drop.")
        # Print the help string specific to this 'database' command.
        typer.echo(ctx.get_help())
        raise typer.Exit()

    logger.info("Database command finished.")


# --- Data Collection Command ---
@app.command(name="policy")
def policy_command(
    # Typer context is passed automatically
    ctx: typer.Context,
    # --- Collection / Processing Options ---
    collect_all: bool = typer.Option(
        False,
        "--collect-all",
        help="Run the full data collection pipeline (crawl and scrape). Mutually exclusive with other actions.",
    ),
    collect_one: Optional[str] = typer.Option(
        None,
        "--collect-one",
        help="Collect and process a single URL. Mutually exclusive with other actions.",
    ),
    crawl_only: bool = typer.Option(
        False,
        "--crawl-all",
        help="Run only the crawling step. Mutually exclusive with other actions.",
    ),
    scrape_only: bool = typer.Option(
        False,
        "--scrape-all",
        help="Run only the scraping/classification step. Mutually exclusive with other actions.",
    ),
    reset_crawl: bool = typer.Option(
        False,
        "--reset-crawl",
        help="Reset crawler state before crawling (used with --crawl-all or --collect-all).",
    ),
    resume_crawl: bool = typer.Option(
        False,
        "--resume-crawl",
        help="Resume crawling from saved state (used with --crawl-all or --collect-all).",
    ),
    # --- Removal Options ---
    remove_id: Optional[int] = typer.Option(
        None,
        "--remove-id",
        help="ID of the policy to remove from DB. Mutually exclusive with other actions.",
    ),
    remove_title: Optional[str] = typer.Option(
        None,
        "--remove-title",
        help="Exact title of the policy to remove from DB. Mutually exclusive with other actions.",
    ),
    force_remove: bool = typer.Option(
        False,
        "--force",
        help="Force removal without confirmation (used with --remove-id or --remove-title).",
    ),
    db_url_remove: Optional[str] = typer.Option(
        None, "--db-url", help="Optional database URL override (for removal action)."
    ),
):
    """
    Manage policy data: Collect, process, or remove policies.

    **Only one primary action (collect, process, or remove) can be performed per command.**

    **Collection/Processing Actions:**
    - `--all`: Runs full data collection (crawl & scrape).
    - `--one <URL>`: Processes a single URL.
    - `--crawl`: Runs only the web crawling part. Use `--reset-crawl` or `--resume-crawl` with this.
    - `--scrape`: Runs only the classification/processing of existing crawled data.

    **Removal Actions:**
    - `--remove-id <ID>`: Removes policy with the given ID and all its data (chunks, images).
    - `--remove-title <TITLE>`: Removes policy with the exact title and all its data.
    - `--force`: Skips confirmation prompt when removing (DANGEROUS).
    - `--db-url`: Specify a DB URL for the removal action (defaults to backend config).
    """
    # Determine which action group is requested
    collection_actions = [collect_all, collect_one is not None, crawl_only, scrape_only]
    removal_actions = [remove_id is not None, remove_title is not None]

    num_collection_actions = sum(collection_actions)
    num_removal_actions = sum(removal_actions)

    # --- Validation: Ensure only one primary action ---
    if num_collection_actions + num_removal_actions == 0:
        # If no action specified, show help.
        print("No action specified for 'policy' command. Choose one action (e.g., --all, --crawl, --remove-id).")
        typer.echo(ctx.get_help())
        raise typer.Exit()
    elif num_collection_actions + num_removal_actions > 1:
        print(
            "ERROR: Multiple actions specified. Choose only one of --all, --one, --crawl, --scrape, --remove-id, or --remove-title."
        )
        typer.echo(ctx.get_help())
        raise typer.Exit(code=1)

    # --- Execute Collection/Processing Action ---
    if num_collection_actions == 1:
        # Get data_collection logger and config
        logger = logging.getLogger("ydrpolicy.data_collection")
        data_config = ctx.meta["data_config"]
        try:
            from ydrpolicy.data_collection import collect_policies, crawl, scrape
        except ImportError as e:
            logger.critical(f"Failed to import data_collection modules: {e}")
            raise typer.Exit(code=1)

        logger.info("Executing policy data collection/processing action...")

        # Update relevant config flags only if doing collection
        data_config.CRAWLER.RESET_CRAWL = reset_crawl
        data_config.CRAWLER.RESUME_CRAWL = resume_crawl and not reset_crawl

        if collect_all:
            logger.info("Running full data collection pipeline...")
            collect_policies.collect_all(config=data_config)
        elif collect_one is not None:
            logger.info(f"Collecting single URL: {collect_one}")
            collect_policies.collect_one(url=collect_one, config=data_config)
        elif crawl_only:
            logger.info("Running crawling step only...")
            crawl.main(config=data_config)
        elif scrape_only:
            logger.info("Running scraping/classification step only...")
            scrape.main(config=data_config)

        logger.info("Policy data collection/processing action finished.")

    # --- Execute Removal Action ---
    elif num_removal_actions == 1:
        # Get backend logger and config
        logger = logging.getLogger("ydrpolicy.backend.scripts")  # Logger for script actions
        backend_config = ctx.meta["backend_config"]
        try:
            from ydrpolicy.backend.scripts.remove_policy import run_remove
        except ImportError as e:
            logger.critical(f"Failed to import remove_policy script: {e}")
            raise typer.Exit(code=1)

        # Determine identifier and type
        identifier = remove_id if remove_id is not None else remove_title
        id_type = "ID" if remove_id is not None else "Title"
        target_db_url = db_url_remove or str(backend_config.DATABASE.DATABASE_URL)

        logger.info(f"Executing remove-policy action for {id_type}: '{identifier}'")

        # Confirmation prompt unless --force is used
        if not force_remove:
            try:
                confirm = typer.confirm(
                    f"==> WARNING <==\nAre you sure you want to permanently remove policy {id_type} '{identifier}' and ALL associated data (chunks, images, history links)? This cannot be undone.",
                    abort=True,  # Abort if user answers no
                )
            except typer.Abort:
                logger.info("Policy removal cancelled by user.")
                raise typer.Exit()  # Exit cleanly
            except EOFError:  # Handle non-interactive environments
                logger.warning("Input stream closed. Assuming cancellation for policy removal.")
                raise typer.Exit()

        logger.warning(f"Proceeding with removal of policy {id_type}: '{identifier}'...")

        # Call the core removal logic function
        success = asyncio.run(run_remove(identifier=identifier, db_url=target_db_url))  # Pass correct db_url

        # Report final status
        if success:
            logger.info(f"SUCCESS: Successfully removed policy identified by {id_type}: '{identifier}'.")
        else:
            logger.error(
                f"FAILURE: Failed to remove policy identified by {id_type}: '{identifier}'. Check logs for details."
            )
            raise typer.Exit(code=1)  # Exit with error code on failure

        logger.info("Remove-policy action finished.")

    else:
        # This case should technically be caught by the initial validation
        logger.error("Internal error: Invalid action state in policy command.")
        raise typer.Exit(code=1)


# --- MCP Server Command ---
@app.command(name="mcp")
def mcp_command(
    # Typer context is passed automatically
    ctx: typer.Context,
    # Allow overriding config values via CLI options
    host: Optional[str] = typer.Option(None, "--host", help="Host address (overrides config). Default from config."),
    port: Optional[int] = typer.Option(None, "--port", help="Port number (overrides config). Default from config."),
    transport: Optional[str] = typer.Option(
        None,
        "--transport",
        help="Transport protocol ('http' or 'stdio', overrides config). Default from config.",
    ),
):
    """
    Start the MCP server to provide tools (like RAG) to compatible clients.

    The MCP server needs to be running for the agent to use the configured tools
    (`find_similar_chunks`, `get_policy_from_ID`).

    Run this in a separate terminal before starting the agent in API mode (`uv run main.py agent`).
    Specify `--transport http` (or rely on default) for API mode.
    Specify `--transport stdio` for direct stdio communication if needed by a client (use with `--no-log` to prevent interference).
    """
    # Get the standard logger instance for MCP tasks.
    logger = logging.getLogger("ydrpolicy.backend.mcp")
    # Retrieve the backend config object from the context.
    backend_config = ctx.meta["backend_config"]
    # Retrieve the logging disabled status from the context.
    log_disabled = ctx.meta["log_disabled"]

    # Import the MCP server module *only when this command is run*.
    try:
        from ydrpolicy.backend.mcp import server as mcp_server
    except ImportError as e:
        logger.critical(f"Failed to import mcp.server module: {e}. Ensure backend components are installed.")
        # print(f"ERROR: Failed to import mcp.server module: {e}.", file=sys.stderr)
        raise typer.Exit(code=1)

    # Determine runtime parameters, using CLI overrides or config defaults.
    run_host = host if host is not None else backend_config.MCP.HOST
    run_port = port if port is not None else backend_config.MCP.PORT
    run_transport = transport if transport is not None else backend_config.MCP.TRANSPORT

    # Warn if running stdio mode with logging potentially active on console
    # The `--no-log` flag is the primary way to silence stdio.
    if run_transport == "stdio" and not log_disabled:
        logger.warning(
            "Running MCP in stdio mode with logging enabled. Console logs might interfere with stdio protocol."
        )
        # More advanced logic could involve temporarily removing console handlers here if needed.

    logger.info(f"Attempting to start MCP server on {run_host}:{run_port} via {run_transport} transport...")
    try:
        # Call the function that contains the server startup logic.
        # This function is blocking and handles server lifecycle.
        mcp_server.start_mcp_server(host=run_host, port=run_port, transport=run_transport)
    except KeyboardInterrupt:
        # Catch interrupt if it happens during the very initial startup phase.
        logger.info("MCP server startup interrupted by user.")
    except Exception as e:
        # Catch other potential errors during startup. Errors during run are logged inside start_mcp_server.
        logger.error(f"MCP server failed to start: {e}", exc_info=True)
        raise typer.Exit(code=1)  # Exit CLI with error code

    # This message might only be reached if the server exits cleanly.
    logger.info("MCP server process finished.")


# --- Agent Command ---
@app.command(name="agent")
def agent_command(
    ctx: typer.Context,
    terminal: bool = typer.Option(False, "--terminal", help="Run agent in terminal (session history only)."),
    no_mcp: bool = typer.Option(False, "--no-mcp", help="Run agent without MCP connection."),
    api_host: Optional[str] = typer.Option(None, "--host", help="Host for FastAPI server (overrides config)."),
    api_port: Optional[int] = typer.Option(None, "--port", help="Port for FastAPI server (overrides config)."),
    api_workers: int = typer.Option(1, "--workers", help="Number of uvicorn workers for API."),
):
    """Run the YDR Policy Chat Agent."""
    logger = logging.getLogger("ydrpolicy.backend.agent")
    backend_config = ctx.meta["backend_config"]
    log_disabled = ctx.meta["log_disabled"]

    logger.info("Executing agent command...")
    use_mcp_flag = not no_mcp
    run_api_host = api_host if api_host is not None else backend_config.API.HOST
    run_api_port = api_port if api_port is not None else backend_config.API.PORT

    logger.info(f"Agent requested mode: {'Terminal' if terminal else 'API'}")
    logger.info(f"MCP Tool Connection: {'Enabled' if use_mcp_flag else 'Disabled'}")

    # --- Execute Terminal Mode ---
    if terminal:
        logger.info("Starting agent in terminal mode (using session history, not persistent)...")
        try:
            from ydrpolicy.backend.agent.policy_agent import create_policy_agent

            # Import SDK components needed for terminal mode run/history
            from agents import Runner, RunResult, RunResultStreaming

            # Import exceptions if needed for more specific handling
            from agents.exceptions import AgentsException, MaxTurnsExceeded
            from openai.types.chat import ChatCompletionMessageParam
        except ImportError as e:
            logger.critical(f"Failed agent import: {e}")
            raise typer.Exit(code=1)

        async def terminal_chat():
            """Async function for terminal chat loop using SDK history."""
            agent_input_list: List[ChatCompletionMessageParam] = []
            agent: Optional[Agent] = None  # Define agent variable
            MAX_HISTORY_TURNS_TERMINAL = 10
            term_logger = logging.getLogger("ydrpolicy.backend.agent.terminal")

            try:
                agent = await create_policy_agent(use_mcp=use_mcp_flag)
                print("\n Yale Radiology Policy Agent (Terminal Mode - Session History)")
                print("-" * 60)
                print(f"MCP Tools: {'Enabled' if use_mcp_flag else 'Disabled'}")
                print("Enter query or 'quit'.")
                print("-" * 60)

                while True:
                    run_succeeded = False  # Track success for history update
                    try:
                        user_input = input("You: ")
                        if user_input.lower() == "quit" or user_input.lower() == "exit":
                            break
                        if not user_input.strip():
                            continue

                        new_user_message: ChatCompletionMessageParam = {
                            "role": "user",
                            "content": user_input,
                        }
                        current_run_input_list = agent_input_list + [new_user_message]

                        print("Agent: ", end="", flush=True)
                        result_stream: Optional[RunResultStreaming] = None  # Hold stream result

                        # --- Run agent and handle stream/errors ---
                        try:
                            result_stream = Runner.run_streamed(
                                starting_agent=agent,
                                input=current_run_input_list,
                            )
                            async for event in result_stream.stream_events():
                                # (Process events: raw_response, tool_call, tool_output etc.)
                                if (
                                    event.type == "raw_response_event"
                                    and hasattr(event.data, "delta")
                                    and event.data.delta
                                ):
                                    print(event.data.delta, end="", flush=True)
                                elif event.type == "run_item_stream_event":
                                    if event.item.type == "tool_call_item":
                                        print(
                                            f"\n[Calling tool: {event.item.tool_call.function.name}...]",
                                            end="",
                                            flush=True,
                                        )
                                    elif event.item.type == "tool_call_output_item":
                                        print(
                                            f"\n[Tool output received.]",
                                            end="",
                                            flush=True,
                                        )
                            # No need to check run_complete_event here, handled by loop finishing

                            # If loop finished without exception, run succeeded
                            run_succeeded = True
                            term_logger.debug("Agent stream completed successfully.")

                        except (
                            AgentsException,
                            MaxTurnsExceeded,
                        ) as agent_err:  # Catch specific agent errors
                            print(f"\n[Agent Error: {agent_err}]")
                            term_logger.error(f"Agent run error: {agent_err}", exc_info=True)
                            # Keep run_succeeded as False
                        except Exception as stream_err:  # Catch other errors during streaming
                            print(f"\n[Error: {stream_err}]")
                            term_logger.error(f"Stream processing error: {stream_err}", exc_info=True)
                            # Keep run_succeeded as False
                        # --- End stream/error handling ---

                        print()  # Newline after agent response/error

                        # --- Update history only on success ---
                        if run_succeeded and result_stream is not None:
                            # Use the streaming result object to get the input list for the next turn
                            # This includes the original input + new items generated during the run
                            agent_input_list = result_stream.to_input_list()
                            term_logger.debug(
                                f"Updated history list via to_input_list(). Length: {len(agent_input_list)}"
                            )
                            # Truncate history
                            if len(agent_input_list) > MAX_HISTORY_TURNS_TERMINAL * 2:
                                agent_input_list = agent_input_list[-(MAX_HISTORY_TURNS_TERMINAL * 2) :]
                                term_logger.debug(f"Truncated history list to {len(agent_input_list)}.")
                        elif not run_succeeded:
                            term_logger.warning("Keeping previous history list due to agent run failure.")
                            # Do not update agent_input_list

                    # Handle outer loop interrupts/errors
                    except EOFError:
                        term_logger.info("EOF received")
                        break
                    except KeyboardInterrupt:
                        term_logger.info("Interrupt received")
                        break
                    except Exception as loop_err:
                        term_logger.error(f"Terminal loop error: {loop_err}", exc_info=True)
                        print(f"\n[Error: {loop_err}]")

            except Exception as start_err:
                term_logger.critical(f"Terminal agent start failed: {start_err}", exc_info=True)
            finally:  # Cleanup
                if use_mcp_flag and agent:
                    term_logger.debug("Closing MCP connection for terminal mode...")
                    try:
                        from ydrpolicy.backend.agent.mcp_connection import (
                            close_mcp_connection,
                        )

                        await close_mcp_connection()
                    except Exception as close_err:
                        term_logger.error(f"MCP close error: {close_err}", exc_info=True)
                term_logger.info("Terminal chat session ended.")

        asyncio.run(terminal_chat())
        logger.info("Terminal agent process finished.")

    # --- Execute API Mode ---
    else:
        logger.info(f"Starting agent via FastAPI server on {run_api_host}:{run_api_port} (History Enabled)...")
        if no_mcp:
            logger.warning("Running API with --no-mcp flag. RAG tools will be unavailable.")
        # (MCP Check logic remains the same)
        if use_mcp_flag:
            import httpx

            mcp_host_for_check = backend_config.MCP.HOST if backend_config.MCP.HOST != "0.0.0.0" else "localhost"
            mcp_base_url = f"http://{mcp_host_for_check}:{backend_config.MCP.PORT}"
            logger.debug(f"Checking MCP server reachability at {mcp_base_url}...")
            try:

                async def check_mcp():
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(mcp_base_url)
                        response.raise_for_status()
                        logger.info(f"MCP server check OK (Status: {response.status_code}).")

                asyncio.run(check_mcp())
            except (httpx.RequestError, httpx.HTTPStatusError) as http_err:
                logger.error(
                    f"MCP server check FAILED at {mcp_base_url}: {http_err}\nEnsure MCP server is running.",
                    exc_info=False,
                )
                raise typer.Exit(code=1)
            except Exception as check_err:
                logger.warning(f"MCP server check error at {mcp_base_url}: {check_err}. Proceeding...")
        # (Run Uvicorn logic remains the same)
        try:
            effective_log_level_name = logging.getLevelName(logging.getLogger().getEffectiveLevel())
            uvicorn.run(
                "ydrpolicy.backend.api_main:app",
                host=run_api_host,
                port=run_api_port,
                workers=api_workers,
                reload=backend_config.API.DEBUG,
                log_level=effective_log_level_name.lower(),
                lifespan="on",
            )
        except Exception as e:
            logger.critical(f"Failed to start FastAPI server: {e}", exc_info=True)
            raise typer.Exit(code=1)


# --- Main Execution Guard ---
if __name__ == "__main__":
    print(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Starting\n{'='*80}")
    app()
    print(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Finished\n{'='*80}")
