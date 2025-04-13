# ydrpolicy/data_collection/scrape/scraper.py

import datetime
import logging
import os
import re
import shutil
import json
from types import SimpleNamespace
from typing import Optional, List # Added List type hint

import pandas as pd
from openai import OpenAI
from pydantic import BaseModel, Field
from tqdm import tqdm

from ydrpolicy.data_collection.scrape.llm_prompts import SCRAPER_LLM_SYSTEM_PROMPT

# Initialize logger
logger = logging.getLogger(__name__)

# Helper function to sanitize policy titles for directory/file names
def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Sanitizes a string to be safe for filenames/directory names."""
    if not name:
        return "untitled_policy"
    # Remove invalid characters (allow alphanumeric, hyphen, underscore)
    sanitized = re.sub(r'[^\w\-]+', '_', name)
    # Remove leading/trailing underscores/hyphens and consolidate multiples
    sanitized = re.sub(r'_+', '_', sanitized).strip('_-')
    # Limit length
    sanitized = sanitized[:max_len]
    # Ensure it's not empty after sanitization
    if not sanitized:
        return "untitled_policy"
    return sanitized


class PolicyExtraction(BaseModel):
    """Schema for the updated OpenAI API response (classification + title)."""
    contains_policy: bool = Field(description="Whether the file contains actual policy text")
    # Added policy_title field as requested by the new prompt
    policy_title: Optional[str] = Field(None, description="Extracted or generated policy title (if contains_policy is true)")
    reasoning: str = Field(description="Reasoning behind the decision")


def _filter_markdown_for_txt(markdown_lines: List[str]) -> str:
    """
    Filters markdown lines to exclude common navigation/menu items for TXT output.
    Expects a list of lines with original line endings.
    """
    filtered_lines = []
    # Prefixes to commonly skip (lists, links, specific headers)
    skip_prefixes = ('* ', '+ ', '- ', '[', '# Content from URL:', '# Final Accessed URL:', '# Retrieved at:')
    # Basic pattern for lines containing only a markdown link
    link_only_pattern = re.compile(r"^\s*\[.*\]\(.*\)\s*$")

    for line in markdown_lines:
        stripped_line = line.strip()
        # Skip empty lines
        if not stripped_line:
            continue
        # Skip lines starting with common nav/list prefixes
        if stripped_line.startswith(skip_prefixes):
            continue
        # Skip lines that contain only a markdown link
        if link_only_pattern.match(stripped_line):
             continue
        # Skip specific known text fragments often found in menus
        if stripped_line in ('MENU', 'Back to Top'):
             continue
        # Exclude lines that look like typical breadcrumbs
        if stripped_line.count('/') > 2 and stripped_line.startswith('/'):
            continue

        # If none of the above, keep the line (with its original ending)
        filtered_lines.append(line)

    # Join the kept lines back into a single string
    return "".join(filtered_lines)


def scrape_policies(
        df: pd.DataFrame,
        base_path: str = None, # Base path to raw markdown files (e.g., MARKDOWN_DIR)
        config: SimpleNamespace = None,
    ) -> pd.DataFrame:
    """
    Processes Markdown files: classifies using LLM (extracting title), and if policy,
    creates a structured output folder (<policy_title>_<timestamp>/...) in scraped_policies.

    Args:
        df (pandas.DataFrame): DataFrame with 'file_path' column (relative to base_path,
                               should point to <timestamp>.md files).
        base_path (str): Base directory of raw markdown files (e.g., config.PATHS.MARKDOWN_DIR).
        config (SimpleNamespace): Configuration object.
        logger (logging.Logger): Logger instance.

    Returns:
        pandas.DataFrame: Original DataFrame updated with classification results,
                          extracted title, and path to the destination 'content.md'.
    """
    if 'file_path' not in df.columns:
        raise ValueError("DataFrame must contain a 'file_path' column.")
    if not base_path:
        raise ValueError("base_path argument is required to locate source markdown files.")

    if not config.LLM.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not found. Cannot perform classification.")
        df['contains_policy'] = False
        df['policy_title'] = None
        df['policy_content_path'] = None
        df['extraction_reasoning'] = "Skipped - No OpenAI API Key"
        return df

    client = OpenAI(api_key=config.LLM.OPENAI_API_KEY)
    # Store results as list of dictionaries before updating DataFrame
    results_list = []
    os.makedirs(config.PATHS.SCRAPED_POLICIES_DIR, exist_ok=True)
    logger.info(f"Target base directory for scraped policies: {config.PATHS.SCRAPED_POLICIES_DIR}")

    # Regex to extract timestamp from raw filename (YYYYMMDDHHMMSSffffff)
    timestamp_pattern = re.compile(r"(\d{20})") # Matches 20 digits

    for index, row in tqdm(df.iterrows(), total=len(df), desc="Classifying & Processing Files"):
        relative_markdown_path = row['file_path']
        source_markdown_path = os.path.normpath(os.path.join(base_path, relative_markdown_path))
        source_filename = os.path.basename(source_markdown_path)

        # Extract timestamp from the source filename (expected format: <timestamp>.md)
        match = timestamp_pattern.search(source_filename)
        raw_timestamp = match.group(1) if match else None
        if not raw_timestamp:
            logger.warning(f"Could not extract timestamp from filename '{source_filename}'. Using fallback. Naming may be inconsistent.")
            raw_timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')

        logger.info(f"\n{'-'*80}")
        logger.info(f"Processing file {index+1}/{len(df)}: {source_markdown_path}")
        logger.info(f"Raw Timestamp: {raw_timestamp}")
        logger.info(f"{'-'*80}")

        # Initialize result dict for this row
        current_result = {
            'contains_policy': False,
            'policy_title': None,
            'policy_content_path': None, # Path to processed content.md
            'reasoning': 'Init Error'
        }

        try:
            if not os.path.exists(source_markdown_path):
                logger.error(f"Source file not found: {source_markdown_path}. Skipping.")
                current_result['reasoning'] = "Source file not found"
                results_list.append(current_result)
                continue

            # Read source markdown content
            with open(source_markdown_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Prepare for LLM call
            system_message = SCRAPER_LLM_SYSTEM_PROMPT # Uses updated prompt
            max_prompt_len = 30000 # Adjust based on model context limits
            content_for_llm = content
            if len(content) > max_prompt_len:
                logger.warning(f"Content length ({len(content)}) exceeds limit ({max_prompt_len}), truncating for LLM.")
                content_for_llm = content[:max_prompt_len] + "\n\n[CONTENT TRUNCATED]"

            # Call OpenAI API using the updated PolicyExtraction model (includes title)
            response = client.beta.chat.completions.parse(
                model=config.LLM.SCRAPER_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"Analyze markdown content from file '{relative_markdown_path}':\n\n{content_for_llm}"}
                ],
                response_format=PolicyExtraction,
            )

            # Parse LLM response
            response_content = response.choices[0].message.content
            llm_result_data = None
            if hasattr(response.choices[0].message, 'refusal') and response.choices[0].message.refusal:
                logger.error(f"API refused to process: {response.choices[0].message.refusal}")
                llm_result_data = {'contains_policy': False, 'policy_title': None, 'reasoning': 'API refused'}
            else:
                try:
                    llm_result_data = json.loads(response_content)
                    # Ensure all expected keys are present, default if necessary
                    llm_result_data.setdefault('contains_policy', False)
                    llm_result_data.setdefault('policy_title', None)
                    llm_result_data.setdefault('reasoning', 'N/A')
                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse LLM response as JSON: {json_err}")
                    logger.error(f"Raw LLM response content: {response_content}")
                    llm_result_data = {'contains_policy': False, 'policy_title': None, 'reasoning': 'LLM JSON parse error'}

            # Update current_result with LLM output
            current_result['contains_policy'] = llm_result_data['contains_policy']
            current_result['policy_title'] = llm_result_data.get('policy_title') # Use .get for optional field
            current_result['reasoning'] = llm_result_data['reasoning']

            logger.info(f"LLM Classification: Contains Policy = {current_result['contains_policy']}")
            logger.info(f"LLM Policy Title: {current_result['policy_title']}")
            logger.info(f"LLM Reasoning: {current_result['reasoning']}")

            # --- Process output structure if classified as policy ---
            if current_result['contains_policy']:
                # Use extracted title (or default) and sanitize it for the folder name
                policy_title_str = current_result['policy_title'] if current_result['policy_title'] else "untitled_policy"
                sanitized_title = sanitize_filename(policy_title_str)

                # Create destination folder name: <sanitized_title>_<raw_timestamp>
                dest_folder_name = f"{sanitized_title}_{raw_timestamp}"
                dest_policy_dir = os.path.join(config.PATHS.SCRAPED_POLICIES_DIR, dest_folder_name)
                os.makedirs(dest_policy_dir, exist_ok=True)
                logger.info(f"Created/Ensured destination directory: {dest_policy_dir}")

                # Define full paths for destination files
                dest_md_path = os.path.join(dest_policy_dir, "content.md")
                dest_txt_path = os.path.join(dest_policy_dir, "content.txt")

                # Define expected source image directory (created by pdf_processor)
                # Structure: <base_path>/<raw_timestamp>/
                source_img_dir = os.path.join(os.path.dirname(source_markdown_path), raw_timestamp)

                try:
                    # 1. Copy the original source markdown file to <dest_policy_dir>/content.md
                    shutil.copy2(source_markdown_path, dest_md_path)
                    logger.info(f"SUCCESS: Copied raw markdown to: {dest_md_path}")
                    current_result['policy_content_path'] = dest_md_path # Store path to content.md

                    # 2. Read the newly copied content.md and create filtered content.txt
                    with open(dest_md_path, 'r', encoding='utf-8') as md_file:
                        markdown_lines = md_file.readlines() # Read lines to preserve endings for filtering
                    filtered_content = _filter_markdown_for_txt(markdown_lines)
                    with open(dest_txt_path, 'w', encoding='utf-8') as txt_file:
                        txt_file.write(filtered_content)
                    logger.info(f"SUCCESS: Created filtered text version at: {dest_txt_path}")

                    # 3. Copy images from source image directory directly into the destination policy directory
                    if os.path.isdir(source_img_dir):
                        logger.info(f"Checking for images in source directory: {source_img_dir}")
                        copied_image_count = 0
                        items_in_source = os.listdir(source_img_dir)
                        if not items_in_source:
                             logger.debug("Source image directory is empty.")
                        else:
                            for item_name in items_in_source:
                                source_item_path = os.path.join(source_img_dir, item_name)
                                # Destination is directly inside destination_policy_dir
                                destination_item_path = os.path.join(dest_policy_dir, item_name)
                                if os.path.isfile(source_item_path):
                                    try:
                                        shutil.copy2(source_item_path, destination_item_path)
                                        copied_image_count += 1
                                    except Exception as img_copy_err:
                                        logger.warning(f"Failed to copy image '{item_name}': {img_copy_err}")
                            if copied_image_count > 0:
                                logger.info(f"SUCCESS: Copied {copied_image_count} image(s) to: {dest_policy_dir}")
                            else:
                                logger.debug("No image files were copied from source directory.")
                    else:
                        logger.debug(f"No source image directory found at: {source_img_dir}")

                except Exception as copy_err:
                    logger.error(f"Error during file processing/copying for {source_markdown_path}: {copy_err}")
                    current_result['policy_content_path'] = None # Reset path on error
                    current_result['reasoning'] += " | File Processing/Copy Error"
            else:
                # If LLM classified as not containing policy
                logger.info("File classified as not containing policy. No output structure created.")
                current_result['policy_content_path'] = None

        except FileNotFoundError:
            logger.error(f"File not found during processing: {source_markdown_path}")
            current_result['reasoning'] = "Source file not found during processing"
        except Exception as e:
            logger.error(f"Unexpected error processing file {source_markdown_path}: {str(e)}", exc_info=True)
            current_result['reasoning'] = f"Unhandled Exception: {str(e)}"

        # Append the result for this row to the list
        results_list.append(current_result)
    # --- End Main Loop ---

    # Update the DataFrame with results from the list
    df = df.copy() # Avoid SettingWithCopyWarning
    df['contains_policy'] = [r.get('contains_policy', False) for r in results_list]
    df['policy_title'] = [r.get('policy_title') for r in results_list] # Add title column
    df['policy_content_path'] = [r.get('policy_content_path') for r in results_list]
    df['extraction_reasoning'] = [r.get('reasoning', 'Unknown Error') for r in results_list]

    # Final summary logging
    logger.info(f"\n{'='*80}\nPOLICY CLASSIFICATION & PROCESSING COMPLETE\n{'='*80}")
    positive_count = sum(df['contains_policy'])
    logger.info(f"Total files processed: {len(df)}")
    logger.info(f"Files classified as containing policies (processed): {positive_count}")
    logger.info(f"Files classified as NOT containing policies: {len(df) - positive_count}")

    return df