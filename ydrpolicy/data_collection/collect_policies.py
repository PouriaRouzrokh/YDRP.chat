# ydrpolicy/data_collection/collect_policies.py

import os
import logging
import sys
import urllib.parse
import re
import datetime
import time
import shutil
import json
from types import SimpleNamespace
from typing import Optional, Tuple, List # Added List

import pandas as pd
from openai import OpenAI
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from dotenv import load_dotenv

from ydrpolicy.data_collection.config import config as default_config

from ydrpolicy.data_collection.crawl.processors.document_processor import (
    download_document as crawl_download_doc,
    convert_to_markdown as crawl_convert_to_md,
    html_to_markdown
)
from ydrpolicy.data_collection.crawl.processors.pdf_processor import (
     pdf_to_markdown as crawl_pdf_to_md # Uses timestamp naming now
)

# Use updated classification+title model and helpers
from ydrpolicy.data_collection.scrape.scraper import PolicyExtraction, _filter_markdown_for_txt, sanitize_filename
from ydrpolicy.data_collection.scrape.llm_prompts import SCRAPER_LLM_SYSTEM_PROMPT

from ydrpolicy.data_collection.crawl.crawl import main as crawl_main
from ydrpolicy.data_collection.scrape.scrape import main as scrape_main

# Initialize logger
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def is_document_url(url: str, config: SimpleNamespace) -> bool:
    """Checks if URL likely points to a document. (Unchanged)"""
    try:
        parsed_url = urllib.parse.urlparse(url); path = parsed_url.path.lower(); extension = os.path.splitext(path)[1]
        if extension and extension in config.CRAWLER.DOCUMENT_EXTENSIONS: return True
        if 'files-profile.medicine.yale.edu/documents/' in url or \
           re.match(r'https://files-profile\.medicine\.yale\.edu/documents/[a-f0-9-]+', url): return True
    except Exception: return False
    return False

# generate_filename_from_url is no longer needed for raw files

# --- Main Collection Functions ---

def collect_one(url: str, config: SimpleNamespace) -> None:
    """Collects, processes, classifies, and copies a single policy URL."""
    logger.info(f"Starting collect_one for URL: {url}")
    logger.warning("Browser opens & pauses for login/navigation.")

    os.makedirs(config.PATHS.MARKDOWN_DIR, exist_ok=True)
    os.makedirs(config.PATHS.SCRAPED_POLICIES_DIR, exist_ok=True)
    os.makedirs(config.PATHS.DOCUMENT_DIR, exist_ok=True)

    markdown_content: Optional[str] = None
    raw_markdown_file_path: Optional[str] = None
    raw_timestamp: Optional[str] = None
    driver: Optional[webdriver.Chrome] = None
    final_url_accessed: str = url

    try:
        # Step 1 & 2: Selenium, Pause, Get Content
        logger.info("Initializing WebDriver...");
        chrome_options = Options(); chrome_options.add_argument("--start-maximized"); chrome_options.add_argument("--disable-notifications"); driver = webdriver.Chrome(options=chrome_options)
        logger.info(f"Navigating to: {url}"); driver.get(url)
        logger.info(">>> PAUSING: Log in/Navigate. Press Enter when ready..."); input(); logger.info(">>> Resuming...")
        final_url_accessed = driver.current_url; logger.info(f"Processing URL after pause: {final_url_accessed}")

        # --- Get Content Logic ---
        if is_document_url(final_url_accessed, config):
            logger.info("Final URL -> Document. Trying OCR/Page Source...")
            doc_output_dir_for_ocr = config.PATHS.MARKDOWN_DIR
            ocr_success = False
            temp_ocr_path: Optional[str] = None # Variable to hold path from OCR
            temp_ocr_ts: Optional[str] = None # Variable to hold timestamp from OCR
            try:
                # Assign tuple return value first
                ocr_result = crawl_pdf_to_md(final_url_accessed, doc_output_dir_for_ocr, config)

                # ** FIX: Unpack ONLY if it's a valid tuple **
                if isinstance(ocr_result, tuple) and len(ocr_result) == 2:
                    temp_ocr_path, temp_ocr_ts = ocr_result
                else:
                    logger.warning("pdf_to_markdown did not return the expected (path, timestamp) tuple.")
                    temp_ocr_path = None
                    temp_ocr_ts = None

                # Check if OCR path is valid and file exists
                if temp_ocr_path and os.path.exists(temp_ocr_path):
                    raw_markdown_file_path = temp_ocr_path # Assign the valid path
                    raw_timestamp = temp_ocr_ts # Assign the valid timestamp
                    with open(raw_markdown_file_path, 'r', encoding='utf-8') as f:
                        markdown_content = f.read()
                    logger.info(f"OCR OK. Len: {len(markdown_content)}. Raw Path: {raw_markdown_file_path}. Timestamp: {raw_timestamp}")
                    ocr_success = True # Mark OCR as successful (path and timestamp are valid)
                else:
                    logger.warning("OCR via pdf_to_markdown failed or returned invalid/non-existent path.")
                    markdown_content = None; raw_markdown_file_path = None; raw_timestamp = None

            except Exception as e:
                logger.warning(f"OCR processing error: {e}", exc_info=True)
                markdown_content = None; raw_markdown_file_path = None; raw_timestamp = None

            # Fallback: Only if OCR didn't succeed
            if not ocr_success:
                 logger.info("OCR failed or TS invalid. Trying page source fallback...")
                 try:
                      WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                      html = driver.page_source;
                      markdown_content = html_to_markdown(html) if html else None
                      if markdown_content: logger.info("Page source fallback OK.")
                      else: logger.warning("Page source fallback empty.")
                 except Exception as e:
                      logger.error(f"Page source fallback error: {e}");
                      markdown_content = None
        else: # Process as Webpage
            logger.info("Final URL -> Webpage. Getting page source...")
            try:
                WebDriverWait(driver, config.CRAWLER.REQUEST_TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(5); # Allow render time
                html = driver.page_source
                if not html or "Login" in html[:500]: logger.warning("HTML empty/login?")
                logger.info(f"HTML length: {len(html) if html else 0}")
                markdown_content = html_to_markdown(html) if html else None;
                logger.info(f"MD length: {len(markdown_content) if markdown_content else 0}")
            except Exception as e:
                logger.error(f"Page source error: {e}");
                markdown_content = None
        # --- End Get Content ---

        # Step 3: Save Retrieved Markdown (if needed) & Ensure Timestamp
        if not markdown_content:
            logger.error(f"Failed get MD for {url} (Final: {final_url_accessed}). Abort.");
            return

        if not raw_markdown_file_path: # If content came from page source, save it now
            logger.info("Saving retrieved content as timestamped raw Markdown...")
            now = datetime.datetime.now()
            raw_timestamp = now.strftime('%Y%m%d%H%M%S%f') # Generate timestamp
            md_filename = f"{raw_timestamp}.md"
            raw_markdown_file_path = os.path.join(config.PATHS.MARKDOWN_DIR, md_filename)
            try:
                header = f"# Source URL: {url}\n# Final URL: {final_url_accessed}\n# Timestamp: {raw_timestamp}\n\n---\n\n"
                with open(raw_markdown_file_path, 'w', encoding='utf-8') as f:
                    f.write(header + markdown_content)
                logger.info(f"Saved Raw Markdown: {raw_markdown_file_path}")
            except Exception as e:
                 logger.error(f"Save MD error {raw_markdown_file_path}: {e}");
                 return
        elif not raw_timestamp: # Should have been caught earlier if path exists
             logger.error("Raw timestamp not determined. Aborting.");
             return

        # Step 4: Classify Saved Markdown & Extract Title
        # (LLM call and processing logic remains the same)
        logger.info(f"Step 4: Classifying {raw_markdown_file_path}...");
        if not config.LLM.OPENAI_API_KEY: logger.error("OPENAI_API_KEY missing."); return
        if not os.path.exists(raw_markdown_file_path): logger.error(f"MD file missing: {raw_markdown_file_path}"); return

        llm_result = {'contains_policy': False, 'policy_title': None, 'reasoning': 'LLM Call Failed'}
        try:
            with open(raw_markdown_file_path, 'r', encoding='utf-8') as f: md_content_llm = f.read()
            client = OpenAI(api_key=config.LLM.OPENAI_API_KEY); system_msg = SCRAPER_LLM_SYSTEM_PROMPT
            logger.debug("Calling OpenAI API for classification and title...")
            user_prompt = f"Analyze file '{os.path.basename(raw_markdown_file_path)}' from URL {url} (Final: {final_url_accessed}):\n\n{md_content_llm[:30000]}{'...[TRUNCATED]' if len(md_content_llm) > 30000 else ''}"
            if len(md_content_llm) > 30000: logger.warning("Truncated content for LLM.")
            response = client.beta.chat.completions.parse(model=config.LLM.SCRAPER_LLM_MODEL, messages=[{"role":"system","content":system_msg},{"role":"user","content":user_prompt}], response_format=PolicyExtraction)
            response_content = response.choices[0].message.content;
            if hasattr(response.choices[0].message, 'refusal') and response.choices[0].message.refusal: logger.error(f"API refused: {response.choices[0].message.refusal}"); llm_result['reasoning'] = 'API refused'
            else:
                 try: llm_result = json.loads(response_content); llm_result.setdefault('contains_policy', False); llm_result.setdefault('policy_title', None); llm_result.setdefault('reasoning', 'N/A')
                 except json.JSONDecodeError as e: logger.error(f"LLM JSON Error: {e}. Raw: {response_content}"); llm_result['reasoning'] = 'LLM JSON error'
            logger.info(f"LLM Classify: Policy? {llm_result['contains_policy']}. Title: {llm_result.get('policy_title')}. Reason: {llm_result.get('reasoning')}")

            # Step 5: Create Structure & Copy if Policy
            # (Logic remains the same, relies on correct raw_timestamp)
            if llm_result['contains_policy']:
                logger.info("Step 5: Creating policy output structure & copying files...")
                source_markdown_path = raw_markdown_file_path
                policy_title_str = llm_result.get('policy_title') or "untitled_policy"
                sanitized_title = sanitize_filename(policy_title_str)
                dest_folder_name = f"{sanitized_title}_{raw_timestamp}" # Use determined raw_timestamp
                dest_policy_dir = os.path.join(config.PATHS.SCRAPED_POLICIES_DIR, dest_folder_name)
                os.makedirs(dest_policy_dir, exist_ok=True)
                dest_md_path = os.path.join(dest_policy_dir, "content.md")
                dest_txt_path = os.path.join(dest_policy_dir, "content.txt")
                source_img_dir = os.path.join(os.path.dirname(source_markdown_path), raw_timestamp)
                try:
                    shutil.copy2(source_markdown_path, dest_md_path); logger.info(f"SUCCESS: Copied MD -> {dest_md_path}")
                    with open(dest_md_path, 'r', encoding='utf-8') as md_f: lines = md_f.readlines()
                    filtered_content = _filter_markdown_for_txt(lines)
                    with open(dest_txt_path, 'w', encoding='utf-8') as txt_f: txt_f.write(filtered_content)
                    logger.info(f"SUCCESS: Created TXT -> {dest_txt_path}")
                    if os.path.isdir(source_img_dir):
                        logger.info(f"Copying images from: {source_img_dir}")
                        count = 0
                        for item in os.listdir(source_img_dir):
                            s=os.path.join(source_img_dir,item); d=os.path.join(dest_policy_dir,item)
                            if os.path.isfile(s):
                                try: shutil.copy2(s, d); count += 1
                                except Exception as e: logger.warning(f"Img copy fail {item}: {e}")
                        logger.info(f"SUCCESS: Copied {count} image(s) -> {dest_policy_dir}")
                    else: logger.debug(f"No image source dir found: {source_img_dir}")
                except Exception as e: logger.error(f"Copy/Process error for {source_markdown_path}: {e}")
            else: logger.info("Step 5: Not policy. No output structure created.")
        except Exception as e: logger.error(f"Classification/Copy error: {e}", exc_info=True)

    except Exception as e: logger.error(f"Critical error collect_one: {e}", exc_info=True)
    finally: # Step 6: Cleanup
        if driver:
            try: driver.quit(); logger.info("WebDriver closed.")
            except Exception as e: logger.error(f"WebDriver quit error: {e}")


# --- collect_all function (Unchanged) ---
def collect_all(config: SimpleNamespace) -> None:
    """Runs the full crawl and scrape (classify/copy) process sequentially."""
    logger.info("Starting collect_all process...")
    logger.info("=" * 80); logger.info("STEP 1: CRAWLING..."); logger.info("=" * 80)
    try: crawl_main(config=config, logger=logger); logger.info("SUCCESS: Crawling process completed.")
    except SystemExit as e: 
        logger.warning(f"Crawling exited code {e.code}.");
        if e.code != 0: logger.error("Aborting collect_all."); return
    except Exception as e: logger.error(f"Crawling failed: {e}", exc_info=True); logger.error("Aborting."); return
    logger.info("=" * 80); logger.info("STEP 2: SCRAPING (Classification & Copy)..."); logger.info("=" * 80)
    try:
        csv_path = os.path.join(config.PATHS.RAW_DATA_DIR, "crawled_policies_data.csv")
        if not os.path.exists(csv_path): logger.error(f"Input file not found: {csv_path}. Aborting scraping."); return
        scrape_main(config=config, logger=logger) # Uses updated scrape_policies
        logger.info("SUCCESS: Scraping process completed.")
    except Exception as e: logger.error(f"Scraping failed: {e}", exc_info=True)
    logger.info("=" * 80); logger.info("SUCCESS: collect_all process finished."); logger.info("=" * 80)

# --- Main execution block ---
if __name__ == "__main__":
    # Setup logging here if run directly (or rely on root config if main.py setup runs first)
    # For direct run, let's configure minimally if no handlers exist
    if not logging.getLogger("ydrpolicy.data_collection").hasHandlers():
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
         print("NOTICE: Basic logging configured for direct script execution.", file=sys.stderr)

    load_dotenv()
    # Use the module-level logger, setup is assumed to be done by main.py or basicConfig above
    logger.info(f"\n{'='*80}\nPOLICY COLLECTION SCRIPT STARTED\n{'='*80}")
    mode = 'one' # Set mode: 'all' or 'one'
    if mode == 'all':
        logger.info("Running collect_all...")
        collect_all(config=default_config) # Removed logger pass
    elif mode == 'one':
        url = "https://files-profile.medicine.yale.edu/documents/d74f0972-b42b-4547-b0f0-41f6a1cf1793"
        logger.info(f"Running collect_one for URL: {url}")
        collect_one(url=url, config=default_config) # Removed logger pass
    else:
        logger.error(f"Invalid mode: {mode}.")
    logger.info("Policy collection script finished.")