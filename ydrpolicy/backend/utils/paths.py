import os
from ydrpolicy.backend.config import config
from ydrpolicy.backend.logger import logger

def ensure_directories():
    """Ensure all required directories exist."""
    for path_name, path_value in vars(config.PATHS).items():
        if isinstance(path_value, str) and not os.path.exists(path_value):
            os.makedirs(path_value, exist_ok=True)
            logger.info(f"Created directory: {path_value}")

# Create a function to get the absolute path from a relative path
def get_abs_path(relative_path):
    """Convert a relative path to absolute path based on the project root."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_dir, relative_path)