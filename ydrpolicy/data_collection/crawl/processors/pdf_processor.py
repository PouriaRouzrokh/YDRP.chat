# ydrpolicy/data_collection/crawl/processors/pdf_processor.py

import os
import base64
import uuid
import logging
import re
import urllib.parse
import datetime
import shutil # Added import
from types import SimpleNamespace
from typing import Tuple, Optional, Dict, List # Added more types

from mistralai import Mistral
from ydrpolicy.data_collection.logger import DataCollectionLogger

logger = DataCollectionLogger(name="pdf_processor", level=logging.INFO)

def generate_pdf_raw_timestamp_name() -> Tuple[str, str]:
    """Generates timestamp-based base name and markdown filename."""
    # (Implementation unchanged)
    now = datetime.datetime.now()
    timestamp_basename = now.strftime('%Y%m%d%H%M%S%f')
    markdown_filename = f"{timestamp_basename}.md"
    return timestamp_basename, markdown_filename

# **** MODIFIED FUNCTION SIGNATURE AND RETURN VALUE ****
def pdf_to_markdown(pdf_url: str, output_folder: str, config: SimpleNamespace) -> Tuple[Optional[str], Optional[str]]:
    """
    Convert PDF to markdown using timestamp naming. Saves MD and images.
    Returns (markdown_path, timestamp_basename) on success, (None, None) on failure.
    """
    markdown_path: Optional[str] = None
    timestamp_basename: Optional[str] = None
    doc_images_dir: Optional[str] = None
    try:
        api_key = config.LLM.MISTRAL_API_KEY
        if not api_key: logger.error("Mistral API key missing."); return None, None
        client = Mistral(api_key=api_key)

        timestamp_basename, markdown_filename = generate_pdf_raw_timestamp_name()
        markdown_path = os.path.join(output_folder, markdown_filename)
        doc_images_dir = os.path.join(output_folder, timestamp_basename)
        os.makedirs(doc_images_dir, exist_ok=True)

        logger.info(f"Processing PDF: {pdf_url}")
        logger.info(f"Raw MD Path: {markdown_path}")
        logger.info(f"Raw Images Path: {doc_images_dir}")

        ocr_response = client.ocr.process(
            model=config.LLM.OCR_MODEL,
            document={"type": "document_url", "document_url": pdf_url},
            include_image_base64=True,
        )
        markdown_content = get_combined_markdown(ocr_response, doc_images_dir)

        with open(markdown_path, 'w', encoding='utf-8') as file:
            file.write(markdown_content)

        logger.info(f"PDF -> Raw MD success: {markdown_path}")
        # **** RETURN TUPLE ****
        return markdown_path, timestamp_basename

    except Exception as e:
        logger.error(f"Error converting PDF {pdf_url} -> MD: {e}", exc_info=True)
        if markdown_path and os.path.exists(markdown_path):
             try: os.remove(markdown_path)
             except OSError: pass
        if doc_images_dir and os.path.exists(doc_images_dir):
             try: shutil.rmtree(doc_images_dir)
             except OSError: pass
        # **** RETURN TUPLE ON FAILURE ****
        return None, None
# **** END MODIFIED FUNCTION ****

# --- save_base64_image, replace_images_in_markdown, get_combined_markdown remain unchanged ---
def save_base64_image(base64_str: str, output_dir: str, img_name: str = None) -> Optional[str]:
    """Saves a base64 encoded image to a file. Returns path or None."""
    if not os.path.exists(output_dir):
        try: os.makedirs(output_dir)
        except OSError as e: logger.error(f"Failed create dir {output_dir}: {e}"); return None
    if img_name is None: img_name = f"image_{uuid.uuid4().hex[:8]}.png"
    elif not any(img_name.lower().endswith(ext) for ext in ['.png','.jpg','.jpeg','.gif','.bmp']): img_name += '.png'
    if ',' in base64_str:
        try: prefix, encoded_data = base64_str.split(',', 1); base64_str = encoded_data
        except ValueError: logger.warning(f"Comma found but couldn't split prefix {img_name}.")
    img_path = os.path.join(output_dir, img_name)
    try:
        img_data = base64.b64decode(base64_str, validate=True)
        with open(img_path, "wb") as img_file: img_file.write(img_data)
        logger.debug(f"Saved image {img_name} to {img_path}")
        return img_path
    except (base64.binascii.Error, ValueError) as decode_err: logger.error(f"Decode error {img_name}: {decode_err}"); return None
    except IOError as io_err: logger.error(f"Save error {img_path}: {io_err}"); return None
    except Exception as e: logger.error(f"Unexpected save error {img_name}: {e}"); return None

def replace_images_in_markdown(markdown_str: str, images_dict: dict, doc_images_dir: str) -> str:
    """Saves images and replaces placeholders with direct filename links."""
    id_to_rel_path = {}
    for img_id, base64_data in images_dict.items():
        filename = f"{img_id}.png"
        saved_path = save_base64_image(base64_data, doc_images_dir, filename)
        if saved_path: relative_image_path = filename; id_to_rel_path[img_id] = relative_image_path; logger.debug(f"Image {img_id} saved, link: {relative_image_path}")
        else: logger.warning(f"Save failed for image {filename}, ID {img_id}.")
    updated_markdown = markdown_str
    for img_id, rel_path in id_to_rel_path.items():
        placeholder = f"![{img_id}]({img_id})"; new_link = f"![{img_id}]({rel_path})"
        updated_markdown = updated_markdown.replace(placeholder, new_link)
        if placeholder not in markdown_str: logger.warning(f"Placeholder '{placeholder}' not found for {img_id}.")
    return updated_markdown

def get_combined_markdown(ocr_response, doc_images_dir: str) -> str:
    """Processes OCR response, saves images, updates links, combines pages."""
    markdowns = []; page_num = 1
    if not hasattr(ocr_response, 'pages') or not ocr_response.pages: logger.warning("OCR response missing pages."); return ""
    for page in ocr_response.pages:
        image_data = {}
        if hasattr(page, 'images') and page.images:
            for img in page.images:
                if hasattr(img, 'id') and hasattr(img, 'image_base64'): image_data[img.id] = img.image_base64
                else: logger.warning(f"Image on page {page_num} lacks id/base64.")
        else: logger.debug(f"No images on page {page_num}.")
        page_markdown = getattr(page, 'markdown', '')
        if not page_markdown: logger.warning(f"No markdown for page {page_num}.")
        updated_markdown = replace_images_in_markdown(page_markdown, image_data, doc_images_dir)
        markdowns.append(updated_markdown); page_num += 1
    return "\n\n---\n\n".join(markdowns)