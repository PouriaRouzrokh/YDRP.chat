# ydrpolicy/data_collection/crawl/crawl.py

import logging
import os
import sys # Import sys for exit
from types import SimpleNamespace

from dotenv import load_dotenv

# Import the updated crawler class
from ydrpolicy.data_collection.crawl.crawler import YaleCrawler
from ydrpolicy.data_collection.config import config as default_config # Renamed import

# Initialize logger
logger = logging.getLogger(__name__)

def main(config: SimpleNamespace = None):
    """Main function to run the crawler."""
    # Load environment variables
    load_dotenv()

    # Use provided config or default
    if config is None:
        config = default_config

    # Validate environment variables potentially needed by processors (e.g., Mistral)
    if not config.LLM.MISTRAL_API_KEY and not os.environ.get("MISTRAL_API_KEY"):
        logger.warning("MISTRAL_API_KEY not found. PDF OCR processing may fail.")

    # Validate environment variables potentially needed by processors (e.g., Mistral)
    if not config.LLM.MISTRAL_API_KEY and not os.environ.get("MISTRAL_API_KEY"):
        logger.warning("MISTRAL_API_KEY not found. PDF OCR processing may fail.")
    else:
        # Ensure config object has the key if loaded from env
        if not config.LLM.MISTRAL_API_KEY:
            config.LLM.MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

    # Handle reset option (overrides resume)
    if config.CRAWLER.RESET_CRAWL:
        # Import here to avoid circular dependency if state manager uses logger
        from ydrpolicy.data_collection.crawl.crawler_state import CrawlerState
        state_manager = CrawlerState(os.path.join(config.PATHS.RAW_DATA_DIR, "state"))
        state_manager.clear_state()
        logger.info("Crawler state has been reset. Starting fresh crawl.")
        # Also clear the output CSV if resetting
        csv_path = os.path.join(config.PATHS.RAW_DATA_DIR, "crawled_policies_data.csv")
        if os.path.exists(csv_path):
            try:
                os.remove(csv_path)
                logger.info(f"Removed existing CSV: {csv_path}")
            except OSError as e:
                logger.error(f"Failed to remove CSV during reset: {e}")


    # Display configuration settings
    logger.info(f"Starting crawler with settings:")
    logger.info(f"  - Start URL: {config.CRAWLER.MAIN_URL}")
    logger.info(f"  - Max Depth: {config.CRAWLER.MAX_DEPTH}")
    logger.info(f"  - Allowed Domains: {config.CRAWLER.ALLOWED_DOMAINS}")
    logger.info(f"  - Resume: {config.CRAWLER.RESUME_CRAWL}")
    logger.info(f"  - Reset: {config.CRAWLER.RESET_CRAWL}")
    logger.info(f"  - Raw Output Dir: {config.PATHS.MARKDOWN_DIR}")
    logger.info(f"  - CSV Log: {os.path.join(config.PATHS.RAW_DATA_DIR, 'crawled_policies_data.csv')}")


    # Initialize and start the crawler using the updated YaleCrawler class
    try:
        # Ensure output directories exist before starting
        os.makedirs(config.PATHS.RAW_DATA_DIR, exist_ok=True)
        os.makedirs(config.PATHS.MARKDOWN_DIR, exist_ok=True)
        os.makedirs(config.PATHS.DOCUMENT_DIR, exist_ok=True)
        os.makedirs(os.path.join(config.PATHS.RAW_DATA_DIR, "state"), exist_ok=True) # State dir

        crawler = YaleCrawler(
            config=config,
        )
        crawler.start() # This now includes the login pause and crawl loop

        logger.info(f"Crawling finished. Raw data saved in {config.PATHS.MARKDOWN_DIR}. See CSV log.")

    except KeyboardInterrupt:
        # Signal handler in YaleCrawler should manage shutdown
        logger.info("KeyboardInterrupt received in main. Crawler shutdown handled internally.")
    except Exception as e:
        logger.error(f"Critical error during crawling: {str(e)}", exc_info=True)
        # Attempt to save state if crawler didn't handle it
        if 'crawler' in locals() and hasattr(crawler, 'save_state') and not crawler.stopping:
             logger.warning("Attempting emergency state save...")
             crawler.save_state()

if __name__ == "__main__":
    # This block is for running the crawl process directly
    print("Yale Medicine Policy Crawler")
    print("============================")
    print("This script crawls Yale Medicine pages, saving raw content.")
    print(f"Raw markdown/images will be saved in '{default_config.PATHS.MARKDOWN_DIR}' using timestamp names.")
    print(f"A CSV log will be created at: '{os.path.join(default_config.PATHS.RAW_DATA_DIR, 'crawled_policies_data.csv')}'")
    print("Press Ctrl+C to stop gracefully (state will be saved).")
    print()

    # Create default logger for direct execution
    log_file_path = getattr(default_config.LOGGING, 'CRAWLER_LOG_FILE', os.path.join(default_config.PATHS.DATA_DIR, "logs", "crawler.log"))
    try:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create log directory {os.path.dirname(log_file_path)}: {e}")
        log_file_path = None # Disable file logging if dir creation fails

    main_logger = logging.getLogger(__name__)
    main_logger.setLevel(logging.INFO)

    main_logger.info(f"\n{'='*80}\nSTARTING CRAWLER PROCESS\n{'='*80}")
    main(config=default_config)
    main_logger.info(f"\n{'='*80}\nCRAWLER PROCESS FINISHED\n{'='*80}")