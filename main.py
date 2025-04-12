#!/usr/bin/env python
# main.py
"""
Main entry point for the YDR Policy RAG Application Engine.
Provides CLI commands for various operational modes:
- database: Manage database schema and population.
- policy: Collect and process policy documents.
- mcp: Start the Model Context Protocol (MCP) server for tools.
- agent: Run the chat agent (via API with history or terminal without).
"""
import asyncio
import os
import sys
from pathlib import Path
from mistralai import Optional
import typer
from typing import List, Optional
import uvicorn # Keep uvicorn import for the agent command

# --- Add project root to sys.path ---
# Ensures modules can be imported correctly when run as a script
try:
    # Assumes main.py is in the project root
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    # Fallback for environments where __file__ might not be defined
    project_root = Path('.').resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# --- Global Imports (Keep minimal) ---
# Import config and logger early as they are used across commands
from ydrpolicy.backend.config import config
from ydrpolicy.backend.logger import BackendLogger
logger = BackendLogger(name="YDRPolicyCLI", path=config.LOGGING.FILE) # Use backend logger path


# --- Typer App Definition ---
app = typer.Typer(
    name="ydrpolicy",
    help="Yale Radiology Policies RAG Application Engine CLI",
    add_completion=False,
    rich_markup_mode="markdown" # Enable rich markup for help text
)

# --- Database Command (Preserved) ---
@app.command(name="database")
def db_command(
    init: bool = typer.Option(False, "--init", help="Initialize the database (create tables, extensions)."),
    populate: bool = typer.Option(False, "--populate", help="Populate the database from processed policies (implies --init)."),
    drop: bool = typer.Option(False, "--drop", help="Drop the database (DANGEROUS!)."),
    force: bool = typer.Option(False, "--force", help="Force drop without confirmation."),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Optional database URL override."), # Added Optional type hint
):
    """
    Manage the application database schema and data.

    - Use `--init` to create tables and extensions if they don't exist.
    - Use `--populate` to **initialize AND populate** the database with policies from the scraped data directory. This is the most common command for setup.
    - Use `--drop --force` to **completely remove** the database (requires confirmation unless `--force` is used).
    """
    # Import database manager only when this command is run
    try:
        from ydrpolicy.backend.database import init_db as db_manager
    except ImportError as e:
        logger.error(f"Failed to import database module: {e}. Ensure backend components are installed.")
        raise typer.Exit(code=1)

    logger.info("Executing database command...")
    if drop:
        logger.warning(f"Database drop requested for URL: {db_url or config.DATABASE.DATABASE_URL}")
        asyncio.run(db_manager.drop_db(db_url=db_url, force=force))
    elif populate:
        logger.info(f"Database initialization and population requested for URL: {db_url or config.DATABASE.DATABASE_URL}")
        asyncio.run(db_manager.init_db(db_url=db_url, populate=True))
    elif init:
        logger.info(f"Database initialization (no population) requested for URL: {db_url or config.DATABASE.DATABASE_URL}")
        asyncio.run(db_manager.init_db(db_url=db_url, populate=False))
    else:
        logger.info("No database action specified. Use --init, --populate, or --drop.")
        # Display help for this command specifically
        ctx = typer.get_current_context()
        print(ctx.get_help())
        raise typer.Exit()
    logger.info("Database command finished.")


# --- Data Collection Command (Preserved) ---
@app.command(name="policy")
def policy_command(
    collect_all: bool = typer.Option(False, "--all", help="Run the full data collection pipeline (crawl and scrape)."),
    collect_one: Optional[str] = typer.Option(None, "--one", help="Collect and process a single URL."), # Added Optional type hint
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
    # Import data collection modules only when this command is run
    try:
        from ydrpolicy.data_collection import collect_policies, crawl, scrape
        from ydrpolicy.data_collection.config import config as data_config
        from ydrpolicy.data_collection.logger import DataCollectionLogger
    except ImportError as e:
        logger.error(f"Failed to import data_collection module: {e}. Ensure data_collection components are installed.")
        raise typer.Exit(code=1)

    # Use a specific logger for data collection tasks if desired, or reuse the main one
    # data_logger = DataCollectionLogger(name="DataCollectionCLI", path=data_config.LOGGING.CRAWLER_LOG_FILE)
    data_logger = logger # Reusing main logger for simplicity here

    logger.info("Executing policy data collection command...")

    # Update data collection config based on flags
    data_config.CRAWLER.RESET_CRAWL = reset_crawl
    # Resume only makes sense if not resetting
    data_config.CRAWLER.RESUME_CRAWL = resume_crawl and not reset_crawl

    if collect_all:
        data_logger.info("Running full data collection pipeline...")
        collect_policies.collect_all(config=data_config, logger=data_logger)
    elif collect_one:
        data_logger.info(f"Collecting single URL: {collect_one}")
        # Assuming collect_one is synchronous; if async, use asyncio.run()
        collect_policies.collect_one(url=collect_one, config=data_config, logger=data_logger)
    elif crawl_only:
        data_logger.info("Running crawling step only...")
        # Assuming crawl.main is synchronous; if async, use asyncio.run()
        crawl.main(config=data_config, logger=data_logger)
    elif scrape_only:
        data_logger.info("Running scraping/classification step only...")
        # Assuming scrape.main is synchronous; if async, use asyncio.run()
        scrape.main(config=data_config, logger=data_logger)
    else:
        logger.info("No policy collection action specified. Use --all, --one, --crawl, or --scrape.")
        ctx = typer.get_current_context()
        print(ctx.get_help())
        raise typer.Exit()
    logger.info("Policy data collection command finished.")


# --- MCP Server Command (Preserved) ---
@app.command(name="mcp")
def mcp_command(
    host: str = typer.Option(config.MCP.HOST, "--host", help="Host address to bind the MCP server to."),
    port: int = typer.Option(config.MCP.PORT, "--port", help="Port number for the MCP server."),
    transport: str = typer.Option(config.MCP.TRANSPORT, "--transport", help="Transport protocol ('http' or 'stdio')."),
):
    """
    Start the MCP server to provide tools (like RAG) to compatible clients.

    The MCP server needs to be running for the agent to use the configured tools
    (`find_similar_chunks`, `get_policy_from_ID`).

    Run this in a separate terminal before starting the agent in API mode.
    """
    # Import MCP server module only when this command is run
    try:
        from ydrpolicy.backend.mcp import server as mcp_server
    except ImportError as e:
        logger.error(f"Failed to import mcp.server module: {e}. Ensure backend components are installed.")
        raise typer.Exit(code=1)

    logger.info(f"Attempting to start MCP server on {host}:{port} via {transport} transport...")
    try:
        # The start_mcp_server function is blocking, so no asyncio.run needed here
        mcp_server.start_mcp_server(host=host, port=port, transport=transport)
    except KeyboardInterrupt:
         logger.info("MCP server stopped by user (KeyboardInterrupt).")
         # Exit gracefully
    except Exception as e:
        logger.error(f"MCP server failed: {e}", exc_info=True)
        raise typer.Exit(code=1)
    logger.info("MCP server process finished.")


# --- Agent Command (Integrated) ---
@app.command(name="agent")
def agent_command(
    terminal: bool = typer.Option(False, "--terminal", help="Run agent in interactive terminal (uses SDK history, not persistent)."), # Updated help
    no_mcp: bool = typer.Option(False, "--no-mcp", help="Run agent without MCP server connection (for testing)."),
    api_host: str = typer.Option(config.API.HOST, "--host", help="Host address for the FastAPI server."),
    api_port: int = typer.Option(config.API.PORT, "--port", help="Port number for the FastAPI server."),
    api_workers: int = typer.Option(1, "--workers", help="Number of uvicorn workers for the API."),
):
    """
    Run the YDR Policy Chat Agent.

    - Default mode starts the **FastAPI server** (`http://<host>:<port>`) which provides a streaming chat endpoint (`/chat/stream`) with **persistent history** stored in the database. Requires the database and MCP server (if not using --no-mcp) to be running.
    - Use `--terminal` for a **command-line chat interface**. This mode uses the SDK's history mechanism (`to_input_list`) for conversational context within the session, but **does not save history** to the database between runs.
    - Use `--no-mcp` to run the agent **without connecting to the MCP server**. RAG tools will be unavailable.
    """ # Updated help
    logger.info("Executing agent command...")

    use_mcp_flag = not no_mcp
    logger.info(f"Agent requested mode: {'Terminal' if terminal else 'API'}")
    logger.info(f"MCP Tool Connection: {'Enabled' if use_mcp_flag else 'Disabled'}")

    if terminal:
        # --- Terminal Mode (Using SDK History) ---
        logger.info("Starting agent in terminal mode (using session history, not persistent)...")
        # Import necessary components for this mode
        try:
            from ydrpolicy.backend.agent.policy_agent import create_policy_agent
            # Use correct top-level imports based on previous check
            from agents import Runner, RunResult, RunResultStreaming
            from agents.run_context import RunStatus
            from agents import RunEvents
            # Type hint for input list (aligns with ChatCompletion API)
            from openai.types.chat import ChatCompletionMessageParam
        except ImportError as e:
             logger.error(f"Failed to import agent modules: {e}. Ensure backend/openai-agents are installed.")
             raise typer.Exit(code=1)

        async def terminal_chat():
            """Async function to handle the terminal chat loop using SDK history."""
            # Start with an empty history list for this session
            agent_input_list: List[ChatCompletionMessageParam] = []
            agent = None
            MAX_HISTORY_TURNS_TERMINAL = 10 # Limit history turns in terminal mode

            try:
                agent = await create_policy_agent(use_mcp=use_mcp_flag)
                print("\n Yale Radiology Policy Agent (Terminal Mode - Session History)")
                print("-" * 60)
                print(f"MCP Tools: {'Enabled' if use_mcp_flag else 'Disabled'}")
                print("Enter your query or type 'quit' to exit.")
                print("-" * 60)

                while True:
                    try:
                        user_input = input("You: ")
                        if user_input.lower() == 'quit':
                            break
                        if not user_input.strip():
                            continue

                        # Prepare input list for the current run
                        new_user_message: ChatCompletionMessageParam = {"role": "user", "content": user_input}
                        # Append new user message to the existing history list
                        current_run_input_list = agent_input_list + [new_user_message]

                        print("Agent: ", end="", flush=True)
                        final_run_result: Optional[RunResult] = None # To store the result object

                        # Run the agent with the structured input list
                        result_stream: RunResultStreaming = Runner.run_streamed(
                            starting_agent=agent,
                            input=current_run_input_list, # Pass the list
                            events_to_record=RunEvents.ALL
                        )

                        # Process the stream for output and capture final result
                        async for event in result_stream.stream_events():
                             if event.type == "raw_response_event" and hasattr(event.data, "delta"):
                                 delta = event.data.delta
                                 if delta:
                                     print(delta, end="", flush=True)
                             elif event.type == "run_item_stream_event":
                                 if event.item.type == "tool_call_item":
                                     tool_name = event.item.tool_call.function.name
                                     print(f"\n[Calling tool: {tool_name}...]", end="", flush=True)
                                 elif event.item.type == "tool_call_output_item":
                                      print(f"\n[Tool output received.]", end="", flush=True)
                             elif event.type == "run_complete_event":
                                  final_run_result = event.result # Capture the final result
                                  break # Streaming done
                        print() # Newline after agent response

                        # Update the history list for the *next* turn using the SDK method
                        if final_run_result and final_run_result.status == RunStatus.COMPLETE:
                             agent_input_list = final_run_result.to_input_list()
                             logger.debug(f"Updated history list for next turn using to_input_list(). Length: {len(agent_input_list)}")
                             # Apply simple truncation based on turns (each turn likely adds user+assistant)
                             if len(agent_input_list) > MAX_HISTORY_TURNS_TERMINAL * 2:
                                 cutoff = len(agent_input_list) - MAX_HISTORY_TURNS_TERMINAL * 2
                                 agent_input_list = agent_input_list[cutoff:]
                                 logger.debug(f"Truncated terminal history list to {len(agent_input_list)} messages.")

                        elif final_run_result: # Handle run failure
                            print(f"\n[Agent run failed: {final_run_result.error}. History might be incomplete for next turn.]")
                            # Keep the old history list on failure
                            logger.warning(f"Keeping previous history list due to agent run failure. Status: {final_run_result.status}")
                        else:
                             print("\n[Agent run did not complete properly. History might be incomplete.]")
                             logger.warning("Agent run did not yield a final result. Keeping previous history list.")

                    except EOFError:
                        print("\nExiting terminal mode (EOF)...")
                        break
                    except KeyboardInterrupt:
                        print("\nExiting terminal mode (Interrupt)...")
                        break
                    except Exception as loop_err:
                         logger.error(f"Error during terminal chat loop: {loop_err}", exc_info=True)
                         print(f"\n[Error occurred: {loop_err}]")

            except Exception as start_err:
                logger.error(f"Failed to initialize or start terminal agent: {start_err}", exc_info=True)
            finally:
                if use_mcp_flag and agent:
                    logger.debug("Closing MCP connection for terminal mode...")
                    from ydrpolicy.backend.agent.mcp_connection import close_mcp_connection
                    await close_mcp_connection()
                logger.info("Terminal chat session ended.")

        asyncio.run(terminal_chat())
        logger.info("Terminal agent process finished.")

    else:
        # --- API Mode (Default - With History Persistence) ---
        logger.info(f"Starting agent via FastAPI server on {api_host}:{api_port} (History Enabled)...")
        if no_mcp:
             # This warning is important as API mode usually implies full functionality
            logger.warning("Running API with --no-mcp flag. RAG tools will be unavailable.")

        # Check if MCP server is likely reachable if MCP is enabled
        if use_mcp_flag:
             # Simple check: Try to connect via HTTP GET to the base URL before starting Uvicorn
             import httpx
             mcp_base_url = f"http://{config.MCP.HOST if config.MCP.HOST != '0.0.0.0' else 'localhost'}:{config.MCP.PORT}"
             try:
                 async def check_mcp():
                     async with httpx.AsyncClient(timeout=5.0) as client:
                         response = await client.get(mcp_base_url)
                         # Basic check, MCP server might not respond to GET / but indicates port is open
                         logger.info(f"MCP server preliminary check at {mcp_base_url} responded (Status: {response.status_code}). Assuming reachable.")
                 asyncio.run(check_mcp())
             except httpx.RequestError as http_err:
                 logger.error(f"MCP server check FAILED at {mcp_base_url}: {http_err}")
                 logger.error("Ensure the MCP server is running (`uv run main.py mcp`) before starting the agent API.")
                 raise typer.Exit(code=1)
             except Exception as check_err:
                 logger.warning(f"MCP server check encountered an error at {mcp_base_url}: {check_err}. Proceeding, but MCP might be unavailable.")


        # Start the Uvicorn server for the FastAPI app
        try:
            uvicorn.run(
                "ydrpolicy.backend.api_main:app", # Point to the FastAPI app instance in api_main.py
                host=api_host,
                port=api_port,
                workers=api_workers,
                reload=config.API.DEBUG, # Enable auto-reload only in debug mode
                log_level=config.LOGGING.LEVEL.lower(), # Sync uvicorn log level with app config
                # Use lifespan="on" to ensure startup/shutdown events fire correctly
                lifespan="on",
            )
        except Exception as e:
            logger.error(f"Failed to start FastAPI server: {e}", exc_info=True)
            raise typer.Exit(code=1)
        # Uvicorn handles its own stop message, logger info might be redundant
        # logger.info("FastAPI server stopped.")


# --- Main Execution Guard ---
if __name__ == "__main__":
    logger.info(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Starting\n{'='*80}")
    # Execute the Typer app
    app()
    logger.info(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Finished\n{'='*80}")