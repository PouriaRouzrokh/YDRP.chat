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

# Import necessary components from agents library
# Lazy/optional imports for 'agents' package to avoid hard dependency for non-agent commands
try:
    from agents.tracing import set_tracing_disabled  # type: ignore
except Exception:  # pragma: no cover - fallback if agents is not installed

    def set_tracing_disabled(_disabled: bool) -> None:  # type: ignore
        return


import typer
import uvicorn
import logging
from openai.types.chat import ChatCompletionMessageParam
import shutil

# No ToolCallItem import needed

# --- Add project root to sys.path ---
# (Keep existing sys.path logic)
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path(".").resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# --- Typer App Definition ---
app = typer.Typer(
    name="ydrpolicy",
    help="Yale Radiology Policies RAG Application Engine CLI",
    add_completion=False,
    rich_markup_mode="markdown",
)


# --- Main App Callback ---
@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    no_log: bool = typer.Option(
        False,
        "--no-log",
        help="Disable ALL logging (console and file). Overrides other log settings.",
        is_eager=True,
    ),
    log_level: Optional[str] = typer.Option(
        None,
        "--log-level",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR). Overrides config.",
        case_sensitive=False,
    ),
    trace: bool = typer.Option(False, "--trace", help="Enable OpenAI trace uploading."),
):
    """
    Main entry point callback. Initializes logging configuration based on flags.
    Stores configuration objects in the Typer context for commands to access.
    """
    try:
        from ydrpolicy.backend.config import config as backend_config
        from ydrpolicy.data_collection.config import config as data_config
    except ImportError as e:
        print(f"ERROR: Failed to import configuration modules: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

    try:
        from ydrpolicy.logging_setup import setup_logging
    except ImportError as e:
        print(f"ERROR: Failed to import logging setup module: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

    ctx.meta["backend_config"] = backend_config
    ctx.meta["data_config"] = data_config
    ctx.meta["log_disabled"] = no_log

    effective_log_level = log_level
    log_disabled_flag = no_log

    if trace:
        print(
            "NOTICE: OpenAI trace uploading enabled via --trace flag.", file=sys.stderr
        )
    else:
        print("NOTICE: OpenAI trace uploading disabled by default.", file=sys.stderr)
        set_tracing_disabled(True)

    setup_logging(
        log_level_str=effective_log_level,
        disable_logging=log_disabled_flag,
        log_to_console=not log_disabled_flag,
    )

    if ctx.invoked_subcommand is None and not ctx.params.get("help"):
        print("No command specified. Use --help to see available commands.")


# --- Database Command ---
@app.command(name="database")
def db_command(
    # Typer context is passed automatically
    ctx: typer.Context,
    # Command-specific options
    init: bool = typer.Option(
        False, "--init", help="Initialize the database (create tables, extensions)."
    ),
    populate: bool = typer.Option(
        False,
        "--populate",
        help="Populate the database from processed policies (implies --init).",
    ),
    drop: bool = typer.Option(False, "--drop", help="Drop the database (DANGEROUS!)."),
    force: bool = typer.Option(
        False, "--force", help="Force drop without confirmation."
    ),
    db_url: Optional[str] = typer.Option(
        None, "--db-url", help="Optional database URL override."
    ),
):
    """
    Manage the application database schema and data.

    - Use `--init` to create tables and extensions if they don't exist.
    - Use `--populate` to **initialize AND populate** the database with policies from the scraped data directory. This is the most common command for setup.
    - Use `--drop --force` to **completely remove** the database (requires confirmation unless `--force` is used).
    """
    logger = logging.getLogger("ydrpolicy.backend.database")
    backend_config = ctx.meta["backend_config"]
    try:
        from ydrpolicy.backend.database import init_db as db_manager
    except ImportError as e:
        logger.error(
            f"Failed to import database module: {e}. Ensure backend components are installed."
        )
        raise typer.Exit(code=1)

    logger.info("Executing database command...")
    target_db_url = db_url or str(backend_config.DATABASE.DATABASE_URL)

    if drop:
        logger.warning(f"Database drop requested for URL: {target_db_url}")
        asyncio.run(db_manager.drop_db(db_url=target_db_url, force=force))
    elif populate:
        logger.info(
            f"Database initialization and population requested for URL: {target_db_url}"
        )
        asyncio.run(db_manager.init_db(db_url=target_db_url, populate=True))
    elif init:
        logger.info(
            f"Database initialization (no population) requested for URL: {target_db_url}"
        )
        asyncio.run(db_manager.init_db(db_url=target_db_url, populate=False))
    else:
        logger.info("No database action specified. Use --init, --populate, or --drop.")
        typer.echo(ctx.get_help())
        raise typer.Exit()
    logger.info("Database command finished.")


# --- Local Ingestion Command (no crawling/scraping) ---
@app.command(name="ingest")
def ingest_command(
    ctx: typer.Context,
    file: Optional[str] = typer.Option(
        None, "--file", help="Filename (or path) of a single local PDF in import dir."
    ),
    csv: Optional[str] = typer.Option(
        None,
        "--csv",
        help="Path to a CSV containing rows: filename,url,origin[,overwrite].",
    ),
    url: Optional[str] = typer.Option(
        None,
        "--url",
        help="If using --file: the online source URL for the file.",
    ),
    origin: str = typer.Option(
        "download",
        "--origin",
        help="If using --file: origin type within Yale site: 'download' (original downloadable file) or 'webpage' (webpage converted to PDF/MD).",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="If using --file: overwrite existing processed TXT if present."
    ),
    clear_db_policies: bool = typer.Option(
        False,
        "--clear-db-policies",
        help="Remove all existing policies, chunks, and images from the database (keeps DB/schema).",
    ),
    clean_files: bool = typer.Option(
        False,
        "--clean-files",
        help="Remove ALL files from import and processed directories, and reset import.csv.",
    ),
):
    """Ingest local files into processed structure and prepare for DB population."""
    logger = logging.getLogger("ydrpolicy.data_collection")
    data_config = ctx.meta["data_config"]

    # Optionally clear all policy records from the DB
    if clear_db_policies:
        logger.warning("Clearing all existing policies from database (chunks/images cascade)...")
        try:
            from ydrpolicy.backend.database.engine import get_async_engine
            from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
            from sqlalchemy import delete
            from ydrpolicy.backend.database.models import Policy, PolicyChunk, Image
            engine = get_async_engine()
            session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            async def _clear():
                async with session_factory() as session:
                    # Delete children first to be explicit
                    await session.execute(delete(PolicyChunk))
                    await session.execute(delete(Image))
                    await session.execute(delete(Policy))
                    await session.commit()
            asyncio.run(_clear())
            logger.info("All policy-related records removed from the database.")
        except Exception as e:
            logger.error(f"Failed to clear policies from DB: {e}")
            raise typer.Exit(code=1)

    # Ensure data directories exist
    try:
        os.makedirs(data_config.PATHS.IMPORT_DIR, exist_ok=True)
        os.makedirs(data_config.PATHS.PROCESSED_DIR, exist_ok=True)
    except Exception:
        pass

    if clean_files:
        logger.warning("Cleaning import and processed directories, and resetting CSV...")
        try:
            # Clean processed dir
            for entry in os.listdir(data_config.PATHS.PROCESSED_DIR):
                try:
                    os.remove(os.path.join(data_config.PATHS.PROCESSED_DIR, entry))
                except IsADirectoryError:
                    shutil.rmtree(os.path.join(data_config.PATHS.PROCESSED_DIR, entry), ignore_errors=True)
                except FileNotFoundError:
                    pass
            # Clean import dir except CSV
            import_csv = os.path.join(data_config.PATHS.IMPORT_DIR, "import.csv")
            for entry in os.listdir(data_config.PATHS.IMPORT_DIR):
                p = os.path.join(data_config.PATHS.IMPORT_DIR, entry)
                if os.path.abspath(p) != os.path.abspath(import_csv):
                    try:
                        os.remove(p)
                    except IsADirectoryError:
                        shutil.rmtree(p, ignore_errors=True)
                    except FileNotFoundError:
                        pass
            # Reset CSV header
            os.makedirs(data_config.PATHS.IMPORT_DIR, exist_ok=True)
            with open(import_csv, "w", encoding="utf-8") as f:
                f.write("filename,url,origin,overwrite\n")
            logger.info("File cleanup completed.")
        except Exception as e:
            logger.error(f"File cleanup failed: {e}")
            raise typer.Exit(code=1)

    # Ingest logic
    if file is None and csv is None:
        # Allow clear-only mode
        logger.info("No --file or --csv provided. Finished housekeeping.")
        return
    if (file is None) == (csv is None) is False:
        # exactly one must be provided if any provided
        print("Specify exactly one of --file or --csv")
        raise typer.Exit(code=1)

    try:
        from ydrpolicy.data_collection.ingest_local_files import (
            ingest_single_file,
            ingest_from_csv,
        )
    except ImportError as e:
        logger.critical(f"Failed to import local ingestion module: {e}")
        raise typer.Exit(code=1)

    if file is not None:
        logger.info(f"Ingesting single file: {file}")
        ok = ingest_single_file(file=file, source_url=url, origin=origin, overwrite=overwrite)
        if not ok:
            logger.error("Single-file ingestion failed.")
            raise typer.Exit(code=1)
        logger.info("Single-file ingestion finished.")
    else:
        logger.info(f"Ingesting from CSV: {csv}")
        success, failed = ingest_from_csv(csv_path=csv)
        if failed > 0 and success == 0:
            raise typer.Exit(code=1)
        logger.info("CSV ingestion finished.")


# --- MCP Server Command ---
@app.command(name="mcp")
def mcp_command(
    ctx: typer.Context,
    host: Optional[str] = typer.Option(
        None, "--host", help="Host address (overrides config). Default from config."
    ),
    port: Optional[int] = typer.Option(
        None, "--port", help="Port number (overrides config). Default from config."
    ),
    transport: Optional[str] = typer.Option(
        None,
        "--transport",
        help="Transport protocol ('http' or 'stdio', overrides config). Default from config.",
    ),
):
    """
    Start the MCP server to provide tools (like RAG) to compatible clients.
    """
    logger = logging.getLogger("ydrpolicy.backend.mcp")
    backend_config = ctx.meta["backend_config"]
    log_disabled = ctx.meta["log_disabled"]
    try:
        from ydrpolicy.backend.mcp import server as mcp_server
    except ImportError as e:
        logger.critical(
            f"Failed to import mcp.server module: {e}. Ensure backend components are installed."
        )
        raise typer.Exit(code=1)

    run_host = host if host is not None else backend_config.MCP.HOST
    run_port = port if port is not None else backend_config.MCP.PORT
    run_transport = transport if transport is not None else backend_config.MCP.TRANSPORT

    if run_transport == "stdio" and not log_disabled:
        logger.warning(
            "Running MCP in stdio mode with console logging potentially enabled (if --no-log not used). "
            "Attempting to disable console handler dynamically."
        )

    logger.info(
        f"Attempting to start MCP server on {run_host}:{run_port} via {run_transport} transport..."
    )
    try:
        mcp_server.start_mcp_server(
            host=run_host, port=run_port, transport=run_transport
        )
    except KeyboardInterrupt:
        logger.info("MCP server startup interrupted by user.")
    except Exception as e:
        logger.error(f"MCP server failed to start or run: {e}", exc_info=False)
        raise typer.Exit(code=1)
    logger.info("MCP server process finished.")


# --- Agent Command ---
@app.command(name="agent")
def agent_command(
    ctx: typer.Context,
    terminal: bool = typer.Option(
        False, "--terminal", help="Run agent in terminal (session history only)."
    ),
    no_mcp: bool = typer.Option(
        False, "--no-mcp", help="Run agent without MCP connection."
    ),
    api_host: Optional[str] = typer.Option(
        None, "--host", help="Host for FastAPI server (overrides config)."
    ),
    api_port: Optional[int] = typer.Option(
        None, "--port", help="Port for FastAPI server (overrides config)."
    ),
    api_workers: int = typer.Option(
        1, "--workers", help="Number of uvicorn workers for API."
    ),
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
        # --- This section remains unchanged and correct ---
        logger.info(
            "Starting agent in terminal mode (using session history, not persistent)..."
        )
        try:
            from ydrpolicy.backend.agent.policy_agent import create_policy_agent
            from agents.mcp import MCPServerSse  # type: ignore
            import contextlib
        except ImportError as e:
            logger.critical(f"Failed agent import: {e}")
            raise typer.Exit(code=1)

        @contextlib.asynccontextmanager
        async def null_async_context(*args, **kwargs):
            yield None

        async def terminal_chat():
            # Lazy imports for agents types to avoid hard dependency for other commands
            try:
                from agents import Agent, Runner, RunResultStreaming  # type: ignore
                from agents.exceptions import AgentsException, MaxTurnsExceeded, UserError  # type: ignore
                from openai.types.chat import ChatCompletionMessageParam  # type: ignore
            except Exception as e:
                term_logger = logging.getLogger("ydrpolicy.backend.agent.terminal")
                term_logger.critical(f"Missing agents dependencies: {e}")
                print(
                    "[Agents dependencies not installed. Install openai-agents to use terminal mode.]"
                )
                return
            agent_input_list: List[ChatCompletionMessageParam] = []
            agent: Optional[Agent] = None
            MAX_HISTORY_TURNS_TERMINAL = 10
            term_logger = logging.getLogger("ydrpolicy.backend.agent.terminal")
            mcp_server_instance: Optional[MCPServerSse] = None
            try:
                agent = await create_policy_agent(use_mcp=use_mcp_flag)
                print(
                    "\n Yale Radiology Policy Agent (Terminal Mode - Session History)"
                )
                print("-" * 60)
                print(f"MCP Tools: {'Enabled' if use_mcp_flag else 'Disabled'}")
                print("Enter query or 'quit'.")
                print("-" * 60)
                if use_mcp_flag and agent and agent.mcp_servers:
                    mcp_server_instance = agent.mcp_servers[0]
                async with (
                    mcp_server_instance
                    if mcp_server_instance
                    and isinstance(mcp_server_instance, MCPServerSse)
                    else null_async_context()
                ) as active_mcp_connection:
                    if use_mcp_flag:
                        if mcp_server_instance and active_mcp_connection is not None:
                            term_logger.info(
                                "Terminal Mode: MCP connection established via async context."
                            )
                        elif mcp_server_instance:
                            term_logger.error(
                                "Terminal Mode: MCP connection failed during context entry."
                            )
                            print(
                                "\n[Error connecting to MCP Tool Server. Tools will be unavailable.]"
                            )
                    while True:
                        run_succeeded = False
                        try:
                            user_input = input("You: ")
                            if user_input.lower() in ["quit", "exit"]:
                                break
                            if not user_input.strip():
                                continue
                            new_user_message: ChatCompletionMessageParam = {
                                "role": "user",
                                "content": user_input,
                            }
                            current_run_input_list = agent_input_list + [
                                new_user_message
                            ]
                            print("Agent: ", end="", flush=True)
                            result_stream: Optional[RunResultStreaming] = None
                            try:
                                if not agent:
                                    print("\n[Critical Error: Agent not initialized.]")
                                    break
                                result_stream = Runner.run_streamed(
                                    starting_agent=agent, input=current_run_input_list
                                )
                                async for event in result_stream.stream_events():
                                    if (
                                        event.type == "raw_response_event"
                                        and hasattr(event.data, "delta")
                                        and event.data.delta
                                    ):
                                        print(event.data.delta, end="", flush=True)
                                    elif event.type == "run_item_stream_event":
                                        if hasattr(event, "item") and hasattr(
                                            event.item, "type"
                                        ):
                                            item: Any = event.item
                                            if item.type == "tool_call_item":
                                                if hasattr(
                                                    item, "raw_item"
                                                ) and hasattr(item.raw_item, "name"):
                                                    tool_name = item.raw_item.name
                                                    print(
                                                        f"\n[Calling tool: {tool_name}...]",
                                                        end="",
                                                        flush=True,
                                                    )
                                                else:
                                                    print(
                                                        f"\n[Calling tool: (unknown name - item.raw_item.name not found)]",
                                                        end="",
                                                        flush=True,
                                                    )
                                                    term_logger.warning(
                                                        "Could not find tool name via item.raw_item.name in tool_call_item."
                                                    )
                                            elif item.type == "tool_call_output_item":
                                                print(
                                                    f"\n[Tool output received.]",
                                                    end="",
                                                    flush=True,
                                                )
                                        else:
                                            term_logger.warning(
                                                f"Received run_item_stream_event without a valid item: {event}"
                                            )
                                run_succeeded = True
                                term_logger.debug(
                                    "Agent stream completed successfully."
                                )
                            except UserError as ue:
                                print(f"\n[Agent UserError: {ue}]")
                                term_logger.error(
                                    f"Agent run UserError: {ue}", exc_info=True
                                )
                                print(
                                    "[MCP Connection error detected. Check MCP server status.]"
                                )
                            except (AgentsException, MaxTurnsExceeded) as agent_err:
                                print(f"\n[Agent Error: {agent_err}]")
                                term_logger.error(
                                    f"Agent run error: {agent_err}", exc_info=True
                                )
                            except AttributeError as ae:
                                print(f"\n[Error processing stream event: {ae}]")
                                term_logger.error(
                                    f"Stream processing AttributeError: {ae}",
                                    exc_info=True,
                                )
                            except Exception as stream_err:
                                print(f"\n[Error: {stream_err}]")
                                term_logger.error(
                                    f"Stream processing error: {stream_err}",
                                    exc_info=True,
                                )
                            print()
                            if run_succeeded and result_stream is not None:
                                agent_input_list = result_stream.to_input_list()
                                term_logger.debug(
                                    f"Updated history list. Length: {len(agent_input_list)}"
                                )
                                if (
                                    len(agent_input_list)
                                    > MAX_HISTORY_TURNS_TERMINAL * 2
                                ):
                                    agent_input_list = agent_input_list[
                                        -(MAX_HISTORY_TURNS_TERMINAL * 2) :
                                    ]
                                    term_logger.debug(
                                        f"Truncated history list to {len(agent_input_list)}."
                                    )
                            elif not run_succeeded:
                                term_logger.warning(
                                    "Keeping previous history list due to agent run failure."
                                )
                        except EOFError:
                            term_logger.info("EOF received")
                            break
                        except KeyboardInterrupt:
                            term_logger.info("Interrupt received")
                            break
                        except Exception as loop_err:
                            term_logger.error(
                                f"Terminal loop error: {loop_err}", exc_info=True
                            )
                            print(f"\n[Error: {loop_err}]")
            except Exception as start_err:
                term_logger.critical(
                    f"Terminal agent start failed: {start_err}", exc_info=True
                )
                print(f"\n[Critical Setup Error: {start_err}]")
            finally:
                term_logger.info("Terminal chat session ended.")
                print("\nExiting terminal mode.")

        asyncio.run(terminal_chat())
        logger.info("Terminal agent process finished.")

    # --- Execute API Mode ---
    else:
        logger.info(
            f"Starting agent via FastAPI server on {run_api_host}:{run_api_port} (History Enabled)..."
        )
        if no_mcp:
            logger.warning(
                "Running API with --no-mcp flag. RAG tools will be unavailable."
            )

        # *******************************************************************
        # REMOVED MCP REACHABILITY CHECK BLOCK
        # The check was unreliable for the SSE endpoint and prevented startup
        # Error handling during connection attempts within ChatService is sufficient.
        # *******************************************************************

        # Start the FastAPI server
        try:
            effective_log_level_name = logging.getLevelName(
                logging.getLogger().getEffectiveLevel()
            )
            uvicorn.run(
                "ydrpolicy.backend.api_main:app",  # Ensure this points to your FastAPI app instance
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
# (Keep existing main execution guard)
if __name__ == "__main__":
    print(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Starting\n{'='*80}")
    app()
    print(f"\n{'='*80}\nYDR Policy RAG Engine CLI - Finished\n{'='*80}")
