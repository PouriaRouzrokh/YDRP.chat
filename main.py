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
import typer
import uvicorn # Needed for running FastAPI app in agent command
import logging # Import standard logging module

# --- Add project root to sys.path ---
# This ensures that modules within the 'ydrpolicy' package can be imported
# correctly when this script is run from the project root directory.
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    # Fallback for environments where __file__ might not be defined (e.g., interactive)
    project_root = Path('.').resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# --- Typer App Definition ---
# Initialize the Typer application which provides the CLI framework.
app = typer.Typer(
    name="ydrpolicy",
    help="Yale Radiology Policies RAG Application Engine CLI",
    add_completion=False, # Disable shell completion for simplicity
    rich_markup_mode="markdown" # Allow Markdown in help strings
)

# --- Main App Callback ---
# This function runs *before* any specific command is executed.
# It's used here to process global flags like --no-log and --log-level,
# and to perform the centralized logging setup.
@app.callback(invoke_without_command=True) # Ensure callback runs even if no command is given
def main_callback(
    ctx: typer.Context, # The Typer context object, used to pass data to commands
    no_log: bool = typer.Option(
        False,
        "--no-log",
        help="Disable ALL logging (console and file). Overrides other log settings.",
        is_eager=True # Process this argument before others, essential for disabling logs early
    ),
    log_level: Optional[str] = typer.Option(
        None,
        "--log-level",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR). Overrides config.",
        case_sensitive=False # Allow lowercase level names
    ),
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
    effective_log_level = log_level # Use CLI override if provided
    log_disabled_flag = no_log

    # Call the centralized setup function to configure Python's standard logging system.
    setup_logging(
        log_level_str=effective_log_level, # Pass level override or None (setup uses config default)
        disable_logging=log_disabled_flag,
        log_to_console= not log_disabled_flag, # Console logging is ON unless explicitly disabled
        # File paths are read directly from the imported configs inside setup_logging
    )

    # Check if a command was actually invoked by the user.
    # If not (e.g., user just ran `uv run main.py`), optionally print help.
    if ctx.invoked_subcommand is None and not ctx.params.get('help'): # Check if built-in help was triggered
        print("No command specified. Use --help to see available commands.")
        # raise typer.Exit() # Optionally exit if no command given


# --- Database Command ---
@app.command(name="database")
def db_command(
    # Typer context is passed automatically
    ctx: typer.Context,
    # Command-specific options
    init: bool = typer.Option(False, "--init", help="Initialize the database (create tables, extensions)."),
    populate: bool = typer.Option(False, "--populate", help="Populate the database from processed policies (implies --init)."),
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

    logger.info("Executing database command...") # Logged only if logging is enabled and level is INFO/DEBUG.
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
    # Command-specific options
    collect_all: bool = typer.Option(False, "--all", help="Run the full data collection pipeline (crawl and scrape)."),
    collect_one: Optional[str] = typer.Option(None, "--one", help="Collect and process a single URL."),
    crawl_only: bool = typer.Option(False, "--crawl", help="Run only the crawling step."),
    scrape_only: bool = typer.Option(False, "--scrape", help="Run only the scraping/classification step (requires crawled data)."),
    reset_crawl: bool = typer.Option(False, "--reset-crawl", help="Reset crawler state before crawling."),
    resume_crawl: bool = typer.Option(False, "--resume-crawl", help="Resume crawling from saved state."),
):
    """
    Collect and process policy documents from Yale sources.

    - Use `--all` to run both crawling and scraping sequentially.
    - Use `--one <URL>` to process a single specific URL.
    - Use `--crawl` to fetch raw content and create markdown files.
    - Use `--scrape` to classify/process existing markdown files into the structured 'scraped_policies' directory.
    - Use `--reset-crawl` to clear saved crawler state.
    - Use `--resume-crawl` to continue a previously stopped crawl.
    """
    # Get the standard logger instance for data collection tasks.
    logger = logging.getLogger("ydrpolicy.data_collection")
    # Retrieve the data collection config object stored in the context.
    data_config = ctx.meta["data_config"]

    # Import data collection modules *only when this command is run*.
    try:
        from ydrpolicy.data_collection import collect_policies, crawl, scrape
        # DataCollectionLogger class is no longer needed here
    except ImportError as e:
        # Use the logger instance we just got, which might be silenced but exists.
        logger.critical(f"Failed to import data_collection modules: {e}. Ensure components are installed.")
        # Use print as a fallback if logging might be entirely disabled.
        # print(f"ERROR: Failed to import data_collection module: {e}.", file=sys.stderr)
        raise typer.Exit(code=1)

    logger.info("Executing policy data collection command...")

    # Update data collection config flags based on CLI options accessed via context parameters.
    data_config.CRAWLER.RESET_CRAWL = ctx.params.get('reset_crawl', False)
    data_config.CRAWLER.RESUME_CRAWL = ctx.params.get('resume_crawl', False) and not data_config.CRAWLER.RESET_CRAWL

    # Retrieve other specific action flags from context parameters.
    collect_one_url = ctx.params.get('collect_one')
    run_crawl_only = ctx.params.get('crawl_only', False)
    run_scrape_only = ctx.params.get('scrape_only', False)

    # Execute the requested data collection action.
    # Pass the standard logger instance down to the functions.
    if collect_all:
        logger.info("Running full data collection pipeline...")
        collect_policies.collect_all(config=data_config, logger=logger)
    elif collect_one_url:
        logger.info(f"Collecting single URL: {collect_one_url}")
        collect_policies.collect_one(url=collect_one_url, config=data_config, logger=logger)
    elif run_crawl_only:
        logger.info("Running crawling step only...")
        crawl.main(config=data_config, logger=logger)
    elif run_scrape_only:
        logger.info("Running scraping/classification step only...")
        scrape.main(config=data_config, logger=logger)
    else:
        # If no valid action specified, show help.
        logger.info("No policy collection action specified. Use --all, --one, --crawl, or --scrape.")
        typer.echo(ctx.get_help())
        raise typer.Exit()

    logger.info("Policy data collection command finished.")


# --- MCP Server Command ---
@app.command(name="mcp")
def mcp_command(
    # Typer context is passed automatically
    ctx: typer.Context,
    # Allow overriding config values via CLI options
    host: Optional[str] = typer.Option(None, "--host", help="Host address (overrides config). Default from config."),
    port: Optional[int] = typer.Option(None, "--port", help="Port number (overrides config). Default from config."),
    transport: Optional[str] = typer.Option(None, "--transport", help="Transport protocol ('http' or 'stdio', overrides config). Default from config."),
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
    if run_transport == 'stdio' and not log_disabled:
         logger.warning("Running MCP in stdio mode with logging enabled. Console logs might interfere with stdio protocol.")
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
        raise typer.Exit(code=1) # Exit CLI with error code

    # This message might only be reached if the server exits cleanly.
    logger.info("MCP server process finished.")


# --- Agent Command ---
@app.command(name="agent")
def agent_command(
    # Typer context is passed automatically
    ctx: typer.Context,
    # Command-specific options
    terminal: bool = typer.Option(False, "--terminal", help="Run agent in interactive terminal (uses SDK history, not persistent)."),
    no_mcp: bool = typer.Option(False, "--no-mcp", help="Run agent without MCP server connection (tools unavailable)."),
    api_host: Optional[str] = typer.Option(None, "--host", help="Host for the FastAPI server (overrides config)."),
    api_port: Optional[int] = typer.Option(None, "--port", help="Port for the FastAPI server (overrides config)."),
    api_workers: int = typer.Option(1, "--workers", help="Number of uvicorn workers for the API."),
):
    """
    Run the YDR Policy Chat Agent.

    - Default mode starts the **FastAPI server** (`http://<host>:<port>`) which provides a streaming chat endpoint (`/chat/stream`) with **persistent history** stored in the database. Requires the database and MCP server (if not using --no-mcp) to be running.
    - Use `--terminal` for a **command-line chat interface**. This mode uses the SDK's history mechanism (`to_input_list`) for conversational context within the session, but **does not save history** to the database between runs.
    - Use `--no-mcp` to run the agent **without connecting to the MCP server**. RAG tools will be unavailable.
    """
    # Get the standard logger instance for agent tasks.
    logger = logging.getLogger("ydrpolicy.backend.agent")
    # Retrieve the backend config object from the context.
    backend_config = ctx.meta["backend_config"]
    # Retrieve the logging disabled status from the context.
    log_disabled = ctx.meta["log_disabled"]

    logger.info("Executing agent command...")

    # Determine agent runtime flags.
    use_mcp_flag = not no_mcp
    # Determine API runtime parameters using CLI overrides or config defaults.
    run_api_host = api_host if api_host is not None else backend_config.API.HOST
    run_api_port = api_port if api_port is not None else backend_config.API.PORT

    logger.info(f"Agent requested mode: {'Terminal' if terminal else 'API'}")
    logger.info(f"MCP Tool Connection: {'Enabled' if use_mcp_flag else 'Disabled'}")

    # --- Execute Terminal Mode ---
    if terminal:
        logger.info("Starting agent in terminal mode (using session history, not persistent)...")
        # Import agent-specific modules needed only for terminal mode.
        try:
            from ydrpolicy.backend.agent.policy_agent import create_policy_agent
            from agents import Runner, RunResult, RunResultStreaming # Use correct top-level imports
            from agents.run_context import RunStatus
            from agents import RunEvents
            from openai.types.chat import ChatCompletionMessageParam # Type hint for history list
        except ImportError as e:
            logger.critical(f"Failed to import agent modules: {e}. Ensure dependencies are installed.")
            # print(f"ERROR: Failed to import agent modules: {e}.", file=sys.stderr)
            raise typer.Exit(code=1)

        async def terminal_chat():
            """Async function to handle the terminal chat loop using SDK history."""
            # Initialize an empty list to store the conversation history for this session.
            agent_input_list: List[ChatCompletionMessageParam] = []
            agent = None # Define agent variable for use in finally block
            MAX_HISTORY_TURNS_TERMINAL = 10 # Limit conversation turns stored in terminal session
            # Get a logger specific to the terminal chat loop
            term_logger = logging.getLogger("ydrpolicy.backend.agent.terminal")

            try:
                # Create the agent instance based on whether MCP tools are enabled.
                agent = await create_policy_agent(use_mcp=use_mcp_flag)

                # Print welcome message.
                print("\n Yale Radiology Policy Agent (Terminal Mode - Session History)")
                print("-" * 60)
                print(f"MCP Tools: {'Enabled' if use_mcp_flag else 'Disabled'}")
                print("Enter your query or type 'quit' to exit.")
                print("-" * 60)

                # Start the interactive chat loop.
                while True:
                    try:
                        # Get user input from the console.
                        user_input = input("You: ")
                        # Check for exit command.
                        if user_input.lower() == 'quit':
                            break
                        # Ignore empty input lines.
                        if not user_input.strip():
                            continue

                        # Create the current user message dictionary.
                        new_user_message: ChatCompletionMessageParam = {"role": "user", "content": user_input}
                        # Prepare the input for the agent by concatenating history and the new message.
                        current_run_input_list = agent_input_list + [new_user_message]

                        print("Agent: ", end="", flush=True) # Print prompt for agent response.
                        final_run_result: Optional[RunResult] = None # Variable to store the final result object.

                        # Execute the agent run in streaming mode.
                        result_stream: RunResultStreaming = Runner.run_streamed(
                            starting_agent=agent,
                            input=current_run_input_list, # Pass the structured list as input.
                            events_to_record=RunEvents.ALL # Record all events for debugging.
                        )

                        # Process the stream of events from the agent run.
                        async for event in result_stream.stream_events():
                             # Handle text deltas for streaming output to console.
                             if event.type == "raw_response_event" and hasattr(event.data, "delta") and event.data.delta:
                                 print(event.data.delta, end="", flush=True)
                             # Handle tool usage events for user feedback.
                             elif event.type == "run_item_stream_event":
                                 if event.item.type == "tool_call_item":
                                     tool_name = event.item.tool_call.function.name
                                     print(f"\n[Calling tool: {tool_name}...]", end="", flush=True)
                                 elif event.item.type == "tool_call_output_item":
                                      print(f"\n[Tool output received.]", end="", flush=True)
                             # Capture the final result object when the run completes.
                             elif event.type == "run_complete_event":
                                  final_run_result = event.result
                                  # No need to break here, stream_events finishes

                        print() # Ensure a newline after the agent's full response.

                        # Update the conversation history list for the *next* turn using the SDK's method.
                        if final_run_result and final_run_result.status == RunStatus.COMPLETE:
                             agent_input_list = final_run_result.to_input_list()
                             term_logger.debug(f"Updated terminal history list using to_input_list(). Length: {len(agent_input_list)}")
                             # Apply simple turn-based truncation to prevent excessive growth in terminal.
                             if len(agent_input_list) > MAX_HISTORY_TURNS_TERMINAL * 2: # Approx messages
                                 cutoff = len(agent_input_list) - MAX_HISTORY_TURNS_TERMINAL * 2
                                 agent_input_list = agent_input_list[cutoff:]
                                 term_logger.debug(f"Truncated terminal history list to {len(agent_input_list)} messages.")
                        # Handle cases where the agent run failed.
                        elif final_run_result:
                            print(f"\n[Agent run failed: {final_run_result.error}. History might be incomplete for next turn.]")
                            term_logger.warning(f"Keeping previous history list due to agent run failure. Status: {final_run_result.status}")
                            # Retain the old agent_input_list if the run failed.
                        else:
                             print("\n[Agent run did not complete properly. History might be incomplete.]")
                             term_logger.warning("Agent run did not yield a final result. Keeping previous history list.")

                    # Handle user interrupts gracefully.
                    except EOFError:
                        term_logger.info("EOF received, exiting terminal mode.")
                        print("\nExiting terminal mode (EOF)...")
                        break
                    except KeyboardInterrupt:
                        term_logger.info("Interrupt received, exiting terminal mode.")
                        print("\nExiting terminal mode (Interrupt)...")
                        break
                    # Catch unexpected errors within the loop.
                    except Exception as loop_err:
                         term_logger.error(f"Error during terminal chat loop: {loop_err}", exc_info=True)
                         print(f"\n[Error occurred: {loop_err}]")

            # Catch errors during agent initialization.
            except Exception as start_err:
                term_logger.error(f"Failed to initialize or start terminal agent: {start_err}", exc_info=True)
            # Cleanup actions after the loop finishes or on error.
            finally:
                # Close the MCP connection if it was used.
                if use_mcp_flag and agent: # Check if agent was successfully created
                    term_logger.debug("Closing MCP connection for terminal mode...")
                    # Import close function only when needed
                    try:
                        from ydrpolicy.backend.agent.mcp_connection import close_mcp_connection
                        await close_mcp_connection()
                    except Exception as close_err:
                         term_logger.error(f"Error closing MCP connection: {close_err}", exc_info=True)
                term_logger.info("Terminal chat session ended.")

        # Run the asynchronous terminal chat function using asyncio.
        asyncio.run(terminal_chat())
        logger.info("Terminal agent process finished.")

    # --- Execute API Mode (Default) ---
    else:
        logger.info(f"Starting agent via FastAPI server on {run_api_host}:{run_api_port} (History Enabled)...")
        if no_mcp:
            # Provide a warning if API mode is run without MCP tools.
            logger.warning("Running API with --no-mcp flag. RAG tools will be unavailable.")

        # Optional: Check if the MCP server is running and reachable before starting the API.
        if use_mcp_flag:
             # Import httpx only if needed for the check
             import httpx
             # Construct the base URL for the MCP server based on config.
             mcp_host_for_check = backend_config.MCP.HOST if backend_config.MCP.HOST != '0.0.0.0' else 'localhost'
             mcp_base_url = f"http://{mcp_host_for_check}:{backend_config.MCP.PORT}"
             logger.debug(f"Checking MCP server reachability at {mcp_base_url}...")
             try:
                 async def check_mcp():
                     # Perform a quick HTTP GET request to check reachability.
                     async with httpx.AsyncClient(timeout=5.0) as client:
                         response = await client.get(mcp_base_url)
                         response.raise_for_status() # Raise exception for 4xx/5xx status
                         # Log success if the server responds positively.
                         logger.info(f"MCP server preliminary check at {mcp_base_url} OK (Status: {response.status_code}).")
                 asyncio.run(check_mcp())
             except httpx.RequestError as http_err:
                 # Log a clear error if the connection fails.
                 logger.error(f"MCP server check FAILED at {mcp_base_url}: {http_err}", exc_info=False)
                 logger.error("Ensure the MCP server is running (`uv run main.py mcp --transport http`) before starting the agent API.")
                 raise typer.Exit(code=1) # Exit if MCP server seems unreachable.
             except httpx.HTTPStatusError as status_err:
                  logger.error(f"MCP server check FAILED at {mcp_base_url}. Server responded with status {status_err.response.status_code}.", exc_info=False)
                  logger.error("Ensure the MCP server is running and healthy.")
                  raise typer.Exit(code=1)
             except Exception as check_err:
                 # Log other errors during the check but allow proceeding, with a warning.
                 logger.warning(f"MCP server check encountered an error at {mcp_base_url}: {check_err}. Proceeding, but MCP might be unavailable.")

        # Start the FastAPI application using Uvicorn.
        try:
            # Determine the actual log level configured by the setup function
            # This ensures Uvicorn matches the potentially overridden level
            effective_log_level_name = logging.getLevelName(logging.getLogger().getEffectiveLevel())

            uvicorn.run(
                "ydrpolicy.backend.api_main:app", # Path to the FastAPI app instance: module:app_variable
                host=run_api_host,
                port=run_api_port,
                workers=api_workers,
                reload=backend_config.API.DEBUG, # Enable auto-reload in debug mode.
                log_level=effective_log_level_name.lower(), # Pass effective level name to uvicorn
                lifespan="on", # Ensure FastAPI lifespan events (startup/shutdown) run.
                # Let uvicorn handle its logging based on the root logger level set previously
                # log_config=None, # Avoid overriding uvicorn's default log config unless necessary
            )
        except Exception as e:
            logger.error(f"Failed to start FastAPI server: {e}", exc_info=True)
            raise typer.Exit(code=1) # Exit CLI with error code

# --- Main Execution Guard ---
# This ensures the code below runs only when the script is executed directly.
if __name__ == "__main__":
    # Print starting message - use print as logging might be disabled by --no-log.
    print(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Starting\n{'='*80}")
    # Run the Typer application. Typer handles argument parsing, executes the
    # main_callback, and then dispatches to the appropriate command function.
    app()
    # Print finished message - use print as logging might be disabled.
    # Note: This message might not appear if a command exits early or raises an exception.
    print(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Finished\n{'='*80}")