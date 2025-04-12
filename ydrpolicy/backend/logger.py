# ydrpolicy/backend/logger.py

import logging
import os
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

class BackendLogger:
    """Custom logger class for the backend using Rich for formatting and file output"""

    def __init__(self, name: str = "BackendLogger", level: int = logging.INFO, path: Optional[str] = None, log_to_console: bool = True): # Added log_to_console
        """Initialize the logger with Rich formatting and file output

        Args:
            name: The name of the logger
            level: The logging level (default: logging.INFO)
            path: Optional file path to save logs. If None, logs will only be displayed in the console
            log_to_console: If True, logs will be output to the console via RichHandler.
        """
        self.console = Console()
        self.logger = logging.getLogger(name) # Get logger instance
        self.logger.setLevel(level) # Set level for this logger

        # Prevent adding handlers multiple times if same name is reused and already configured
        if self.logger.hasHandlers():
             # Simple clear assuming re-configuration is intended if called again
            self.logger.handlers.clear()

        # Prevent messages from propagating to the root logger
        self.logger.propagate = False # <-- IMPORTANT for avoiding duplicates

        log_init_message = f"Backend logging initialized for '{name}'"

        # Add Rich handler for terminal output ONLY if requested
        if log_to_console:
            rich_handler = RichHandler(
                rich_tracebacks=True,
                console=self.console,
                show_time=True,
                show_path=False
            )
            rich_handler.setLevel(level)
            self.logger.addHandler(rich_handler)
            log_init_message += " (Console ON)"
        else:
             log_init_message += " (Console OFF)"


        # Add file handler if a log file is specified
        if path and path != "":
            try:
                log_dir = os.path.dirname(path)
                if log_dir: # Ensure log_dir is not empty if path is just a filename
                     os.makedirs(log_dir, exist_ok=True)
                else:
                    # Handle case where path is just filename in current dir
                    path = os.path.join(os.getcwd(), path) # Or choose a default dir

                file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                file_handler = logging.FileHandler(path, mode='a', encoding='utf-8')
                file_handler.setFormatter(file_formatter)
                file_handler.setLevel(level)
                self.logger.addHandler(file_handler)
                log_init_message += f". Log file: {path}"
            except Exception as e:
                # Log error using the already configured console handler (if present) or print
                error_msg = f"Failed to initialize file logging to {path} for '{name}': {e}"
                if log_to_console:
                    self.logger.error(error_msg, exc_info=True)
                else: # If console logging is off, print error as fallback
                     print(f"ERROR: {error_msg}", file=sys.stderr)
                log_init_message += " (File logging FAILED)"
        else:
            log_init_message += " (File logging OFF)"

        # Log initialization message *once* after handlers are set
        # Use level=logging.INFO directly on the underlying logger
        # to bypass potential level filters on handlers if needed for this message.
        self.logger.log(logging.INFO, log_init_message)


    # --- Logging methods remain the same ---
    def info(self, message: str) -> None:
        self.logger.info(message)
    # ... (error, debug, warning, success, failure, etc.) ...
    def error(self, message: str, exc_info=False) -> None:
        self.logger.error(message, exc_info=exc_info)
    def debug(self, message: str) -> None:
        self.logger.debug(message)
    def warning(self, message: str) -> None:
        self.logger.warning(message)
    def success(self, message: str) -> None:
        self.logger.info(f"[green]SUCCESS:[/green] {message}")
    def failure(self, message: str, exc_info=False) -> None:
        self.logger.error(f"[red]FAILURE:[/red] {message}", exc_info=exc_info)
    def progress(self, message: str) -> None:
        self.logger.info(f"[blue]PROGRESS:[/blue] {message}")
    def db(self, message: str) -> None:
        self.logger.info(f"[yellow]DATABASE:[/yellow] {message}")
    def api(self, message: str) -> None:
        self.logger.info(f"[magenta]API:[/magenta] {message}")
    def vector(self, message: str) -> None:
        self.logger.info(f"[cyan]VECTOR:[/cyan] {message}")


# --- NO DEFAULT INSTANCE CREATION ---