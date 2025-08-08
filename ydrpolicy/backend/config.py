"""
Configuration settings for the Yale Radiology Policies RAG backend components.
"""

import os
from types import SimpleNamespace
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Create config dictionary first
_config_dict = {
    # Data directory settings
    "PATHS": {
        "DATA_DIR": os.path.join(_BASE_DIR, "data"),
        # "DATA_DIR": os.path.join(_BASE_DIR, "tests", "data_collection", "test_data"),
        "AUTH_DIR": os.path.join(_BASE_DIR, "auth"),
    },
    # Database settings
    "DATABASE": {
        "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql+asyncpg://pr555:@localhost:5432/ydrpolicy"),
        # "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql+asyncpg://pouria:@localhost:5432/ydrpolicy"),
        "POOL_SIZE": 5,
        "MAX_OVERFLOW": 10,
        "POOL_TIMEOUT": 30,
        "POOL_RECYCLE": 1800,  # 30 minutes
    },
    # RAG settings
    "RAG": {
        "CHUNK_SIZE": 1000,
        "CHUNK_OVERLAP": 200,
        "SIMILARITY_THRESHOLD": 0.2,  # Minimum similarity score for a match
        "TOP_K": 10,  # Number of chunks to retrieve
        "VECTOR_WEIGHT": 0.8,  # Weight for vector search vs keyword search
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "EMBEDDING_DIMENSIONS": 1536,  # Dimensions for the embedding vectors
    },
    # OpenAI settings
    "OPENAI": {
        "API_KEY": os.environ.get("OPENAI_API_KEY"),
        # "MODEL": "gpt-5",  # Default model for chat
        "MODEL": "o4-mini",  # Default model for chat
        "TEMPERATURE": 0.7,
        "MAX_TOKENS": 4000,
    },
    # MCP server settings
    "MCP": {
        "HOST": "0.0.0.0",
        "PORT": 8001,
        "TRANSPORT": "http",  # http or stdio
    },
    # API server settings
    "API": {
        "HOST": "0.0.0.0",
        "PORT": 8000,
        "DEBUG": False,
        "CORS_ORIGINS": ["http://localhost:3000", "https://ydrp.chat"],
        # --- JWT Settings ---
        "JWT_SECRET": os.environ.get(
            "JWT_SECRET", "a_very_insecure_default_secret_key_please_change"
        ),  # CHANGE THIS IN .env!
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRATION": 30,  # Default: Access tokens expire in 30 minutes
    },
    # Logging settings
    "LOGGING": {
        "LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
        "FILE": None,  # Default to None, path will be set below
        "DISABLED": False,  # Flag to globally disable logging
    },
}

# Add other path-dependent settings to the config dictionary
_config_dict["PATHS"]["RAW_DATA_DIR"] = os.path.join(_config_dict["PATHS"]["DATA_DIR"], "raw")
_config_dict["PATHS"]["PROCESSED_DATA_DIR"] = os.path.join(_config_dict["PATHS"]["DATA_DIR"], "processed")
_config_dict["PATHS"]["SCRAPED_POLICIES_DIR"] = os.path.join(
    _config_dict["PATHS"]["PROCESSED_DATA_DIR"], "scraped_policies"
)
_config_dict["PATHS"]["USERS_SEED_FILE"] = os.path.join(_config_dict["PATHS"]["AUTH_DIR"], "users.json")
_config_dict["PATHS"]["LOGS_DIR"] = os.path.join(_config_dict["PATHS"]["DATA_DIR"], "logs")
_config_dict["LOGGING"] = {
    "LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
    "FILE": os.path.join(_config_dict["PATHS"]["DATA_DIR"], "logs", "backend.log"),
}


# Convert nested dictionaries to SimpleNamespace objects recursively
def dict_to_namespace(d):
    if isinstance(d, dict):
        for key, value in d.items():
            d[key] = dict_to_namespace(value)
        return SimpleNamespace(**d)
    return d


# Create the config object with nested namespaces
config = dict_to_namespace(_config_dict)


# Function to override config values from environment variables
def load_config_from_env():
    """Load configuration values from environment variables."""

    if os.environ.get("OPENAI_API_KEY"):
        config.OPENAI.API_KEY = os.environ.get("OPENAI_API_KEY")

    if os.environ.get("JWT_SECRET"):
        config.API.JWT_SECRET = os.environ.get("JWT_SECRET")


# Load environment-specific settings
load_config_from_env()
