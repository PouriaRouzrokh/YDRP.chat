import logging
from pydantic import BaseModel
from rich.console import Console
from rich.logging import RichHandler

# Define the structured output format
class AgentResponse(BaseModel):
    handoff: bool
    response: str

class ChatLogger:
    """Custom logger class using Rich for formatting"""
    
    def __init__(self, name: str = "ChatAgent", level: int = logging.INFO):
        """Initialize the logger with Rich formatting"""
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True)]
        )
        self.logger = logging.getLogger(name)
        self.console = Console()
        
    def info(self, message: str) -> None:
        """Log info level message"""
        self.logger.info(message)
        
    def error(self, message: str) -> None:
        """Log error level message"""
        self.logger.error(message)
        
    def debug(self, message: str) -> None:
        """Log debug level message"""
        self.logger.debug(message)
        
    def warning(self, message: str) -> None:
        """Log warning level message"""
        self.logger.warning(message)