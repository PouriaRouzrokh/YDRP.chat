# ydrpolicy/data_collection/scrape/scrape.py

import logging
import os
from types import SimpleNamespace

import pandas as pd
from dotenv import load_dotenv

from ydrpolicy.data_collection.scrape.scraper import (
    scrape_policies,
)  # Uses the updated function
from ydrpolicy.data_collection.config import config as default_config  # Renamed import

# Initialize logger
logger = logging.getLogger(__name__)


def main(config: SimpleNamespace = None):
    """Main function to run the policy classification and processing step."""
    # Load environment variables if not already loaded
    load_dotenv()

    # Use provided config or default
    if config is None:
        config = default_config

    # Get the path to the crawled policies data CSV
    crawled_policies_data_path = os.path.join(config.PATHS.RAW_DATA_DIR, "crawled_policies_data.csv")

    # Validate environment variables needed for scraping
    if not config.LLM.OPENAI_API_KEY and not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found. Policy classification will be skipped.")
        # Exiting might be appropriate if classification is essential
        # return
    else:
        # Ensure config object has the key if loaded from env
        if not config.LLM.OPENAI_API_KEY:
            config.LLM.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

    # Ensure output directory exists
    try:
        os.makedirs(config.PATHS.SCRAPED_POLICIES_DIR, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create output directory {config.PATHS.SCRAPED_POLICIES_DIR}: {e}")
        return  # Cannot proceed without output directory

    # Log configuration settings relevant to scraping
    logger.info(f"Starting policy classification/processing with:")
    logger.info(f"  - Input CSV: {crawled_policies_data_path}")
    logger.info(f"  - Raw Markdown Base Path: {config.PATHS.MARKDOWN_DIR}")  # Base path for source MD files
    logger.info(f"  - Output Directory: {config.PATHS.SCRAPED_POLICIES_DIR}")
    logger.info(f"  - Classification LLM model: {config.LLM.SCRAPER_LLM_MODEL}")

    # Check if input CSV exists
    if not os.path.exists(crawled_policies_data_path):
        logger.error(f"Input data file not found: {crawled_policies_data_path}")
        logger.error("Please run the crawling step first or ensure the file exists.")
        return

    # Read the original data (output from crawler)
    try:
        logger.info(f"Reading input data from: {crawled_policies_data_path}")
        original_df = pd.read_csv(crawled_policies_data_path)
        # Check if necessary column exists
        if "file_path" not in original_df.columns:
            logger.error("Input CSV must contain a 'file_path' column pointing to raw markdown files.")
            return
        if original_df.empty:
            logger.warning("Input CSV is empty. No files to process.")
            return
    except Exception as e:
        logger.error(f"Failed to read input CSV {crawled_policies_data_path}: {e}")
        return

    # Run the classification and processing
    # Pass the MARKDOWN_DIR as the base_path where the relative paths in the CSV can be found
    df_processed = scrape_policies(
        original_df,
        base_path=config.PATHS.MARKDOWN_DIR,  # Critical: Point to where raw MD files are
        config=config,
    )

    # Save the updated DataFrame (includes classification results and output paths)
    output_path = os.path.join(config.PATHS.PROCESSED_DATA_DIR, "processed_policies_log.csv")  # Changed name slightly
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)  # Ensure processed dir exists
        logger.info(f"Saving processing log to: {output_path}")
        df_processed.to_csv(output_path, index=False)
        logger.info("Policy classification and processing completed successfully.")
    except Exception as e:
        logger.error(f"Failed to save processed log CSV {output_path}: {e}")


if __name__ == "__main__":
    from ydrpolicy.data_collection.config import config as main_config

    print("Yale Medicine Policy Scraper (Classifier & Processor)")
    print("===================================================")
    print("This script classifies crawled markdown files and processes policies.")
    print(f"Results will be structured in: {main_config.PATHS.SCRAPED_POLICIES_DIR}")
    print()

    # Create default logger for direct execution
    log_file = getattr(
        main_config.LOGGING,
        "SCRAPER_LOG_FILE",
        os.path.join(main_config.PATHS.DATA_DIR, "logs", "scraper.log"),
    )
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    main_logger = logging.getLogger(__name__)
    main_logger.setLevel(logging.INFO)
    main_logger.info("\n" + "=" * 80 + "\nSTARTING POLICY CLASSIFICATION & PROCESSING\n" + "=" * 80)

    main_logger.info("\n" + "=" * 80 + "\nSTARTING POLICY CLASSIFICATION & PROCESSING\n" + "=" * 80)
    main(config=main_config)
    main_logger.info("\n" + "=" * 80 + "\nPOLICY CLASSIFICATION & PROCESSING FINISHED\n" + "=" * 80)
