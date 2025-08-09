# ydrpolicy/logging_setup.py
"""
Centralized logging configuration for the YDR Policy RAG application.

This module provides a single function `setup_logging` to configure
the standard Python logging system based on application configuration
and command-line flags.
"""
import logging
import os
import sys
from typing import Optional

# Import Rich library components for console handling
from rich.console import Console
from rich.logging import RichHandler

# Import configurations from both backend and data_collection parts
# to access log paths, levels, and the disabled flag.
try:
    from ydrpolicy.backend.config import config as backend_config
    from ydrpolicy.data_collection.config import config as data_config
except ImportError as e:
    print(
        f"CRITICAL ERROR: Could not import configuration modules for logging setup: {e}",
        file=sys.stderr,
    )
    print(
        "Ensure configuration files exist and Python path is correct.", file=sys.stderr
    )
    sys.exit(1)  # Exit if config cannot be loaded, as logging setup is fundamental


def setup_logging(
    log_level_str: Optional[str] = None,
    disable_logging: bool = False,
    log_to_console: bool = True,
    # Default file paths read from respective configs
    backend_log_file: Optional[str] = backend_config.LOGGING.FILE,
    dc_log_file_crawler: Optional[str] = data_config.LOGGING.CRAWLER_LOG_FILE,
    dc_log_file_scraper: Optional[str] = data_config.LOGGING.SCRAPER_LOG_FILE,
    # Add specific file for collect_policy_urls if desired
    dc_log_file_collect: Optional[str] = None,  # Or maybe reuse crawler log?
):
    """
    Configures logging handlers and levels for the entire application.

    Should be called once at application startup (e.g., in main.py callback)
    after command-line arguments (like --no-log or --log-level) are processed.

    Sets up handlers for console and separate files for backend and data collection.

    Args:
        log_level_str: The desired logging level (e.g., "INFO", "DEBUG").
                       Defaults to backend config level if None.
        disable_logging: If True, disables all logging handlers globally.
        log_to_console: If True, adds a console handler (RichHandler) to the root logger.
        backend_log_file: Path for the backend file log. Defaults to backend config.
        dc_log_file_crawler: Path for the data collection crawler file log. Defaults to data collection config.
        dc_log_file_scraper: Path for the data collection scraper file log. Defaults to data collection config.
        dc_log_file_collect: Path for the combined data collection file log (optional).
    """
    # --- Global Disable Check ---
    if disable_logging:
        # Configure root logger with NullHandler to silence everything, preventing
        # "No handlers could be found" warnings from libraries.
        logging.basicConfig(
            level=logging.CRITICAL + 1, force=True, handlers=[logging.NullHandler()]
        )
        # A direct print indicates why no logs will appear.
        print("NOTICE: Logging setup skipped as logging is disabled.", file=sys.stderr)
        return  # Stop setup

    # --- Determine Log Level ---
    # Use provided level string, fallback to backend config level, default to INFO
    effective_level_str = log_level_str or backend_config.LOGGING.LEVEL or "INFO"
    log_level = getattr(logging, effective_level_str.upper(), logging.INFO)

    # --- Configure Root Logger ---
    # Configure the root logger first. Handlers added here will see logs
    # from all modules unless propagation is disabled on specific loggers.
    root_logger = logging.getLogger()  # Get the root logger
    root_logger.handlers.clear()  # Remove any predefined handlers (e.g., from basicConfig)
    root_logger.setLevel(log_level)  # Set the minimum level for the root

    # --- Shared Formatter for Files ---
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # List to gather status messages for final log entry
    init_messages = [f"Logging configured. Level: {effective_level_str.upper()}"]

    # --- Console Handler (Rich) - Added to Root Logger ---
    if log_to_console:
        # Create a RichHandler for pretty console output (sent to stderr)
        rich_handler = RichHandler(
            rich_tracebacks=True,
            console=Console(stderr=True),  # Ensure logs go to stderr
            show_time=True,
            show_path=False,
            log_time_format="[%X]",  # e.g., [14:30:59]
        )
        rich_handler.setLevel(log_level)
        # Add the console handler to the root logger
        root_logger.addHandler(rich_handler)
        init_messages.append("Console logging: ON")
    else:
        init_messages.append("Console logging: OFF")

    # --- Setup Function for File Handlers (Helper) ---
    def _add_file_handler(
        logger_instance: logging.Logger, file_path: Optional[str], file_desc: str
    ) -> None:
        """Adds a file handler to a specific logger instance."""
        if file_path:
            try:
                log_dir = os.path.dirname(file_path)
                # Create directory if it doesn't exist
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                # Handle case where path might be just a filename (use current dir)
                else:
                    file_path = os.path.join(os.getcwd(), file_path)

                # Create and configure the file handler
                file_handler = logging.FileHandler(
                    file_path, mode="a", encoding="utf-8"
                )
                file_handler.setFormatter(file_formatter)
                file_handler.setLevel(log_level)
                # Add the handler to the specific logger instance
                logger_instance.addHandler(file_handler)
                init_messages.append(f"{file_desc} File logging: ON ({file_path})")
            except Exception as e:
                # Print error directly as logger setup might be failing
                print(
                    f"ERROR setting up {file_desc.lower()} file log '{file_path}': {e}",
                    file=sys.stderr,
                )
                init_messages.append(f"{file_desc} File logging: FAILED")
        else:
            init_messages.append(f"{file_desc} File logging: OFF")

    # --- Backend Logger Configuration ---
    backend_logger = logging.getLogger("ydrpolicy.backend")
    backend_logger.setLevel(log_level)  # Set level for this specific branch
    backend_logger.propagate = True  # Allow messages to reach root handlers (console)
    backend_logger.handlers.clear()  # Clear only specific handlers if needed
    _add_file_handler(backend_logger, backend_log_file, "Backend")

    # --- Data Collection Logger Configuration ---
    dc_logger = logging.getLogger("ydrpolicy.data_collection")
    dc_logger.setLevel(log_level)
    dc_logger.propagate = True  # Allow messages to reach root handlers (console)
    dc_logger.handlers.clear()
    # Add handlers for specific data collection logs if needed (or use one combined)
    # Example: Separate files for crawl/scrape based on provided paths
    # Note: A single file handler on dc_logger would capture all data collection logs.
    # If using separate files, ensure the correct path is passed from main.py or config.
    _add_file_handler(dc_logger, dc_log_file_crawler, "DC-Crawler")
    _add_file_handler(dc_logger, dc_log_file_scraper, "DC-Scraper")
    # _add_file_handler(dc_logger, dc_log_file_collect, "DC-Collect") # If using combined

    # --- Log Initialization Summary ---
    # Use the root logger to log the final setup status
    logging.getLogger().info(" | ".join(init_messages))

    # --- Optional: Adjust Library Log Levels ---
    # Reduce noise from verbose libraries if necessary
    # logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO) # Or WARNING
    # logging.getLogger("httpx").setLevel(logging.WARNING)
