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
        # "DATA_DIR": os.path.join(_BASE_DIR, "data"),
        "DATA_DIR": os.path.join(_BASE_DIR, "tests", "data_collection", "test_data"),
    },
    "LLM": {
        "MISTRAL_API_KEY": os.environ.get("MISTRAL_API_KEY"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "CRAWLER_LLM_MODEL": "o3-mini",  # Should be a reasoning model from OpenAI
        "SCRAPER_LLM_MODEL": "o3-mini",  # Should be a reasoning model from OpenAI
        "OCR_MODEL": "mistral-ocr-latest",
    },
    "CRAWLER": {
        "MAIN_URL": "https://medicine.yale.edu/diagnosticradiology/facintranet/policies",
        "ALLOWED_DOMAINS": ["yale.edu", "medicine.yale.edu"],
        "DOCUMENT_EXTENSIONS": [".pdf", ".doc", ".docx"],
        "ALLOWED_EXTENSIONS": [".pdf", ".doc", ".docx", ".html", ".htm", ".php", ".aspx"],
        "PRIORITY_KEYWORDS": [
            "policy",
            "policies",
            "guideline",
            "guidelines",
            "procedure",
            "procedures",
            "protocol",
            "protocols",
            "radiology",
            "diagnostic",
            "imaging",
            "safety",
            "radiation",
            "contrast",
            "mri",
            "ct",
            "ultrasound",
            "xray",
            "x-ray",
            "regulation",
            "requirement",
            "compliance",
            "standard",
            "documentation",
        ],
        "FOLLOW_DEFINITE_LINKS_ONLY": False,  # If False, follow both "definite" and "probable" links
        "MAX_DEPTH": 6,
        "REQUEST_TIMEOUT": 90,
        "WAIT_TIME": 90,
        "RESUME_CRAWL": False,
        "RESET_CRAWL": False,
        "SAVE_INTERVAL": 10,
    },
    "LOGGING": {
        "LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
        "FILE": None,  # Default to None, path will be set below
        "DISABLED": False,  # Flag to globally disable logging
    },
}

# Add other path-dependent settings to the config dictionary

_config_dict["PATHS"]["RAW_DATA_DIR"] = os.path.join(_config_dict["PATHS"]["DATA_DIR"], "raw")
_config_dict["PATHS"]["DOCUMENT_DIR"] = os.path.join(_config_dict["PATHS"]["RAW_DATA_DIR"], "documents")
_config_dict["PATHS"]["MARKDOWN_DIR"] = os.path.join(_config_dict["PATHS"]["RAW_DATA_DIR"], "markdown_files")
_config_dict["PATHS"]["PROCESSED_DATA_DIR"] = os.path.join(_config_dict["PATHS"]["DATA_DIR"], "processed")
_config_dict["PATHS"]["SCRAPED_POLICIES_DIR"] = os.path.join(
    _config_dict["PATHS"]["PROCESSED_DATA_DIR"], "scraped_policies"
)
_config_dict["LOGGING"] = {
    "LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
    "CRAWLER_LOG_FILE": os.path.join(_config_dict["PATHS"]["DATA_DIR"], "logs", "crawler.log"),
    "SCRAPER_LOG_FILE": os.path.join(_config_dict["PATHS"]["DATA_DIR"], "logs", "scraper.log"),
}


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
    if os.environ.get("MISTRAL_API_KEY"):
        config.LLM.MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
    if os.environ.get("OPENAI_API_KEY"):
        config.LLM.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


# Load environment-specific settings
load_config_from_env()
