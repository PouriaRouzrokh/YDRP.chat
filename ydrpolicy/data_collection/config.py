"""
Configuration settings for the YDR Policy Data Collection.
"""

import os
from types import SimpleNamespace
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

_config_dict = {
    "PATHS": {
        "DATA_DIR": os.path.join(_BASE_DIR, "data"),
    },
}

# Add other path-dependent settings to the config dictionary

_config_dict["PATHS"]["IMPORT_DIR"] = os.path.join(
    _config_dict["PATHS"]["DATA_DIR"], "import"
)
_config_dict["PATHS"]["PROCESSED_DIR"] = os.path.join(
    _config_dict["PATHS"]["DATA_DIR"], "processed"
)
_config_dict["PATHS"]["SOURCE_POLICIES_DIR"] = os.path.join(_BASE_DIR, "data", "source_policies")


# Convert nested dictionaries to SimpleNamespace objects recursively
def dict_to_namespace(d):
    if isinstance(d, dict):
        for key, value in d.items():
            d[key] = dict_to_namespace(value)
        return SimpleNamespace(**d)
    return d


# Convert dictionary to an object with attributes
config = dict_to_namespace(_config_dict)


# Function to override config values from environment variables
def load_config_from_env():
    """Load configuration values from environment variables."""
    if os.environ.get(" OPENAI_API_KEY"):
        config.LLM.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


# Load environment-specific settings
load_config_from_env()
