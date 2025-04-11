# ydrpolicy/data_collection/logger.py

import logging
import os
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Assuming config is correctly imported if needed, but it seems unused here directly
# from ydrpolicy.data_collection.config import config

class DataCollectionLogger:
    """Custom logger class using Rich for formatting and file output"""

    def __init__(self, name: str = "DataCollectionLogger", level: int = logging.INFO, path: Optional[str] = None):
        """Initialize the logger with Rich formatting and file output

        Args:
            name: The name of the logger
            level: The logging level (default: logging.INFO)
            path: Optional file path to save logs. If None, logs will only be displayed in the console
        """
        # Create a Rich console
        self.console = Console()

        # Create the logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Remove any existing handlers to avoid duplicates
        if self.logger.hasHandlers():
             self.logger.handlers.clear()

        # Add Rich handler for terminal output with nice formatting
        rich_handler = RichHandler(
            rich_tracebacks=True,
            console=self.console,
            show_time=True,
            show_path=False # Keep path off for cleaner logs unless needed
        )
        rich_handler.setLevel(level)
        self.logger.addHandler(rich_handler)

        # Add file handler if a log file is specified
        if path:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                # Standard formatter for file logs
                file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

                # Create and configure file handler
                # Use 'a' for append mode
                file_handler = logging.FileHandler(path, mode='a', encoding='utf-8')
                file_handler.setFormatter(file_formatter)
                file_handler.setLevel(level)

                # Add file handler to the logger
                self.logger.addHandler(file_handler)

                # Log that we initialized with a file
                # Use logger directly to ensure it goes to file if console handler level is higher
                self.logger.log(logging.INFO, f"Logging initialized. Log file: {path}")
            except Exception as e:
                 # Log error about file handler creation to console via RichHandler if possible
                 self.logger.log(logging.ERROR, f"Failed to initialize file logging to {path}: {e}", exc_info=True)
                 self.logger.log(logging.INFO, "Logging initialized (console only due to file error)")

        else:
            self.logger.log(logging.INFO, "Logging initialized (console only)")

    # --- MODIFICATION: Accept exc_info argument ---
    def info(self, message: str, exc_info=False) -> None:
        """Log info level message"""
        self.logger.info(message, exc_info=exc_info)

    def error(self, message: str, exc_info=False) -> None:
        """Log error level message"""
        self.logger.error(message, exc_info=exc_info)

    def debug(self, message: str, exc_info=False) -> None:
        """Log debug level message"""
        self.logger.debug(message, exc_info=exc_info)

    def warning(self, message: str, exc_info=False) -> None:
        """Log warning level message"""
        self.logger.warning(message, exc_info=exc_info)
    # --- END MODIFICATION ---

    def success(self, message: str) -> None:
        """Log success as an info message with success prefix"""
        self.logger.info(f"[green]SUCCESS:[/green] {message}")

    # --- MODIFICATION: Pass exc_info for failure ---
    def failure(self, message: str, exc_info=False) -> None:
        """Log failure as an error message with failure prefix"""
        self.logger.error(f"[red]FAILURE:[/red] {message}", exc_info=exc_info)
    # --- END MODIFICATION ---

    def progress(self, message: str) -> None:
        """Log progress as an info message with progress prefix"""
        self.logger.info(f"[blue]PROGRESS:[/blue] {message}")