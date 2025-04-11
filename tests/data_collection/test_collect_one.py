# tests/data_collection/test_collect_one.py

import sys
import os
import logging
import time
import re # Import re for timestamp matching
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

from ydrpolicy.data_collection.collect_policies import collect_one
from ydrpolicy.data_collection.config import config
from ydrpolicy.data_collection.logger import DataCollectionLogger

def test_collect_one():
    """
    Tests the collect_one function checking the new output structure
    (<title>_<timestamp>/...). Requires manual interaction.
    """
    print("--- Setting up test configuration ---")
    test_data_dir = os.path.join(project_root, "test_data")
    print(f"Test data will be stored in: {test_data_dir}")

    # --- Override config paths ---
    config.PATHS.DATA_DIR = test_data_dir
    config.PATHS.RAW_DATA_DIR = os.path.join(config.PATHS.DATA_DIR, "raw")
    config.PATHS.DOCUMENT_DIR = os.path.join(config.PATHS.RAW_DATA_DIR, "documents")
    config.PATHS.MARKDOWN_DIR = os.path.join(config.PATHS.RAW_DATA_DIR, "markdown_files")
    config.PATHS.PROCESSED_DATA_DIR = os.path.join(config.PATHS.DATA_DIR, "processed")
    config.PATHS.SCRAPED_POLICIES_DIR = os.path.join(config.PATHS.PROCESSED_DATA_DIR, "scraped_policies")
    test_log_dir = os.path.join(config.PATHS.DATA_DIR, "logs")
    os.makedirs(test_log_dir, exist_ok=True)
    test_log_file = os.path.join(test_log_dir, "collect_one_test.log")
    config.LOGGING.COLLECT_ONE_LOG_FILE = test_log_file

    # --- Ensure API keys ---
    config.LLM.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    config.LLM.MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
    if not config.LLM.OPENAI_API_KEY: print("WARNING: OPENAI_API_KEY missing.")
    if not config.LLM.MISTRAL_API_KEY: print("WARNING: MISTRAL_API_KEY missing.")

    # --- Define Test URL ---
    test_url = "https://medicine.yale.edu/diagnosticradiology/patientcare/policies/intraosseousneedlecontrastinjection/"
    # test_url = "https://files-profile.medicine.yale.edu/documents/dd571fd1-6b49-4f74-a8d6-2d237919270c"
    print(f"Test URL: {test_url}")

    # --- Logger ---
    test_logger = DataCollectionLogger(name="collect_one_test", level=logging.INFO, path=test_log_file)
    test_logger.info("--- Starting test_collect_one ---")

    policy_output_dir = None
    try:
        # Ensure parent directories exist
        os.makedirs(config.PATHS.MARKDOWN_DIR, exist_ok=True)
        os.makedirs(config.PATHS.SCRAPED_POLICIES_DIR, exist_ok=True)

        collect_one(url=test_url, config=config, logger=test_logger)
        test_logger.info("--- collect_one function finished ---")
        print("--- collect_one function finished ---")

        # --- **MODIFIED** Assertions for new structure ---
        print("--- Running Assertions ---")
        raw_markdown_files_found = []
        if os.path.exists(config.PATHS.MARKDOWN_DIR):
            raw_markdown_files_found = [f for f in os.listdir(config.PATHS.MARKDOWN_DIR) if f.endswith('.md') and re.match(r"\d{20}\.md", f)]
        print(f"Raw Timestamped Markdown files found ({len(raw_markdown_files_found)}): {raw_markdown_files_found}")
        assert len(raw_markdown_files_found) > 0, "No raw timestamped markdown file was created."

        # Find the policy directory created within scraped_policies (expecting <title>_<timestamp> format)
        policy_dirs_found = []
        expected_dir_pattern = re.compile(r".+_\d{20}$") # Ends with _<20-digit-timestamp>
        if os.path.exists(config.PATHS.SCRAPED_POLICIES_DIR):
             policy_dirs_found = [d for d in os.listdir(config.PATHS.SCRAPED_POLICIES_DIR)
                                  if os.path.isdir(os.path.join(config.PATHS.SCRAPED_POLICIES_DIR, d)) and expected_dir_pattern.match(d)]

        print(f"Processed Policy output directories found ({len(policy_dirs_found)}): {policy_dirs_found}")
        assert len(policy_dirs_found) > 0, "No processed policy output directory (<title>_<timestamp>) was created."

        # Check contents of the first directory found
        policy_output_dir_name = policy_dirs_found[0]
        policy_output_dir = os.path.join(config.PATHS.SCRAPED_POLICIES_DIR, policy_output_dir_name)
        print(f"Checking contents of: {policy_output_dir}")

        content_md_path = os.path.join(policy_output_dir, "content.md")
        content_txt_path = os.path.join(policy_output_dir, "content.txt")

        assert os.path.exists(content_md_path), f"content.md not found in {policy_output_dir}"
        print(f"Found: {content_md_path}")
        assert os.path.exists(content_txt_path), f"content.txt not found in {policy_output_dir}"
        print(f"Found: {content_txt_path}")

        # Check size comparison
        md_size = os.path.getsize(content_md_path)
        txt_size = os.path.getsize(content_txt_path)
        print(f"Size Check: content.md={md_size} bytes, content.txt={txt_size} bytes")
        assert txt_size <= md_size, "content.txt is larger than content.md (filtering failed?)"
        # If filtering is expected for this URL, uncomment:
        # assert txt_size < md_size, "content.txt filtering did not reduce size"

        # Check for images directly in the policy dir
        images_in_policy_dir = [f for f in os.listdir(policy_output_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        print(f"Images found in policy dir ({len(images_in_policy_dir)}): {images_in_policy_dir}")
        # assert len(images_in_policy_dir) > 0, "Expected images but none found."

        print("--- Structure assertions passed ---")

    except Exception as e:
        test_logger.error(f"Error during test_collect_one: {e}", exc_info=True)
        print(f"ERROR during test_collect_one: {e}")
        raise

if __name__ == "__main__":
    print("Running test_collect_one directly...")
    test_collect_one()
    print("Test finished. Check 'test_data' directory for output.")