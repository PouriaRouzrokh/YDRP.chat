# ydrpolicy/data_collection/process_local_pdfs.py

import logging
import os
import re
import shutil
from typing import Optional

from ydrpolicy.data_collection.config import config as data_config
from ydrpolicy.data_collection.processors.pdf_processor import pdf_file_to_markdown
from ydrpolicy.data_collection.scrape.scraper import (
    _filter_markdown_for_txt,
    sanitize_filename,
)


logger = logging.getLogger(__name__)


def _find_latest_policies_dir(base_dir: str) -> Optional[str]:
    if not os.path.isdir(base_dir):
        logger.error(f"Source policies base directory not found: {base_dir}")
        return None
    latest_dir: Optional[str] = None
    latest_key: Optional[int] = None
    pattern = re.compile(r"^policies_(\d{8})$")
    for name in os.listdir(base_dir):
        full = os.path.join(base_dir, name)
        if not os.path.isdir(full):
            continue
        m = pattern.match(name)
        if not m:
            continue
        try:
            key = int(m.group(1))
        except ValueError:
            continue
        if latest_key is None or key > latest_key:
            latest_key = key
            latest_dir = full
    return latest_dir


def process_all_local_pdfs(
    source_policies_root: Optional[str] = None, global_download_url: Optional[str] = None
) -> None:
    """
    Process all local PDFs found under the specified or latest `policies_YYYYMMDD` directory.
    Produces processed folders under `LOCAL_POLICIES_DIR` and appends to processed_policies_log.csv.
    """
    base_dir = data_config.PATHS.SOURCE_POLICIES_DIR
    root_dir = source_policies_root or _find_latest_policies_dir(base_dir)
    if not root_dir or not os.path.isdir(root_dir):
        logger.error(f"Local policies directory not found or invalid: {root_dir}")
        return

    logger.info(f"Processing local PDFs under: {root_dir}")
    local_policies_dir = data_config.PATHS.LOCAL_POLICIES_DIR
    os.makedirs(local_policies_dir, exist_ok=True)

    csv_log_path = os.path.join(
        data_config.PATHS.PROCESSED_DATA_DIR, "processed_policies_log.csv"
    )
    csv_header = (
        "url,file_path,include,found_links_count,definite_links,probable_links,timestamp,"
        "contains_policy,policy_title,policy_content_path,extraction_reasoning\n"
    )
    if not os.path.exists(csv_log_path):
        try:
            with open(csv_log_path, "w", encoding="utf-8") as f:
                f.write(csv_header)
        except Exception as e:
            logger.warning(f"Could not create CSV log at {csv_log_path}: {e}")

    processed_count = 0
    skipped_count = 0
    error_count = 0

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if not filename.lower().endswith(".pdf"):
                continue
            pdf_path = os.path.join(dirpath, filename)
            ok = _process_single_pdf(
                pdf_path=pdf_path,
                global_download_url=global_download_url,
                csv_log_path=csv_log_path,
                local_policies_dir=local_policies_dir,
            )
            if ok:
                processed_count += 1
            else:
                skipped_count += 1

    logger.info(
        f"Local PDF processing finished. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}"
    )


def process_one_pdf(pdf_path: str, global_download_url: Optional[str] = None) -> bool:
    """Process a single local PDF into the processed folder and update CSV."""
    local_policies_dir = data_config.PATHS.LOCAL_POLICIES_DIR
    os.makedirs(local_policies_dir, exist_ok=True)
    csv_log_path = os.path.join(
        data_config.PATHS.PROCESSED_DATA_DIR, "processed_policies_log.csv"
    )
    if not os.path.exists(csv_log_path):
        csv_header = (
            "url,file_path,include,found_links_count,definite_links,probable_links,timestamp,"
            "contains_policy,policy_title,policy_content_path,extraction_reasoning\n"
        )
        try:
            with open(csv_log_path, "w", encoding="utf-8") as f:
                f.write(csv_header)
        except Exception as e:
            logger.warning(f"Could not create CSV log at {csv_log_path}: {e}")
    return _process_single_pdf(
        pdf_path=pdf_path,
        global_download_url=global_download_url,
        csv_log_path=csv_log_path,
        local_policies_dir=local_policies_dir,
    )


def _process_single_pdf(
    pdf_path: str,
    global_download_url: Optional[str],
    csv_log_path: str,
    local_policies_dir: str,
) -> bool:
    try:
        if not os.path.isfile(pdf_path):
            logger.warning(f"PDF not found: {pdf_path}")
            return False
        title_pretty = _prettify_title_from_filename(pdf_path)
        md_output_dir = data_config.PATHS.MARKDOWN_DIR
        os.makedirs(md_output_dir, exist_ok=True)
        md_path, raw_timestamp = pdf_file_to_markdown(pdf_path, md_output_dir, data_config)
        if not md_path or not os.path.exists(md_path) or not raw_timestamp:
            logger.warning(f"OCR/Markdown conversion failed for PDF. Skipping: {pdf_path}")
            return False

        scrape_timestamp = raw_timestamp
        try:
            with open(md_path, "r", encoding="utf-8") as f_md:
                raw_md_content = f_md.readlines()
            text_content = _filter_markdown_for_txt(raw_md_content)
            header_lines = [
                f"# Source URL: {global_download_url or ''}",
                f"# Imported From: Local PDF",
                f"# Original File: {os.path.basename(pdf_path)}",
                f"# Timestamp: {scrape_timestamp}",
                "\n---\n\n",
            ]
            markdown_content = "".join(header_lines) + "".join(raw_md_content)
        except Exception as e:
            logger.error(f"Failed to prepare markdown/text for '{pdf_path}': {e}")
            return False

        folder_name = f"{sanitize_filename(title_pretty)}_{scrape_timestamp}"
        dest_folder = os.path.join(local_policies_dir, folder_name)
        try:
            os.makedirs(dest_folder, exist_ok=True)
            dest_md_path = os.path.join(dest_folder, "content.md")
            dest_txt_path = os.path.join(dest_folder, "content.txt")
            with open(dest_md_path, "w", encoding="utf-8") as f_md_out:
                f_md_out.write(markdown_content)
            with open(dest_txt_path, "w", encoding="utf-8") as f_txt:
                f_txt.write(text_content)
            source_img_dir = os.path.join(md_output_dir, scrape_timestamp)
            if os.path.isdir(source_img_dir):
                copied = 0
                for item in os.listdir(source_img_dir):
                    s = os.path.join(source_img_dir, item)
                    d = os.path.join(dest_folder, item)
                    if os.path.isfile(s):
                        try:
                            shutil.copy2(s, d)
                            copied += 1
                        except Exception as img_err:
                            logger.warning(
                                f"Failed to copy image '{item}' for '{title_pretty}': {img_err}"
                            )
                if copied:
                    logger.info(
                        f"Copied {copied} image(s) to '{dest_folder}' for '{title_pretty}'."
                    )
        except Exception as e:
            logger.error(f"Failed to write structured files for '{title_pretty}': {e}")
            return False

        try:
            url_field = (global_download_url or "").strip()
            file_basename = os.path.basename(dest_md_path)
            include = True
            found_links_count = 0
            definite_links = "[]"
            probable_links = "[]"
            timestamp_field = scrape_timestamp
            contains_policy = True
            policy_title_field = title_pretty
            policy_content_path = dest_md_path
            reasoning_field = "Imported from local PDFs"
            row = f'{url_field},{file_basename},{str(include)},{found_links_count},"{definite_links}","{probable_links}",{timestamp_field},{str(contains_policy)},{policy_title_field},{policy_content_path},{reasoning_field}\n'
            with open(csv_log_path, "a", encoding="utf-8") as f:
                f.write(row)
        except Exception as log_err:
            logger.warning(f"Failed to append to processed_policies_log.csv: {log_err}")
        return True
    except Exception as e:
        logger.error(f"Unexpected error processing PDF '{pdf_path}': {e}")
        return False


def _prettify_title_from_filename(name: str) -> str:
    base = os.path.splitext(os.path.basename(name))[0]
    pretty = re.sub(r"[_\-]+", " ", base).strip()
    pretty = re.sub(r"\s+", " ", pretty)
    return pretty or base


