# ydrpolicy/data_collection/processors/pdf_processor.py

import os
import base64
import uuid
import logging
import datetime
import shutil
from types import SimpleNamespace
from typing import Tuple, Optional

from mistralai import Mistral
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def generate_pdf_raw_timestamp_name() -> Tuple[str, str]:
    now = datetime.datetime.now()
    timestamp_basename = now.strftime("%Y%m%d%H%M%S%f")
    markdown_filename = f"{timestamp_basename}.md"
    return timestamp_basename, markdown_filename


def pdf_url_to_markdown(
    pdf_url: str, output_folder: str, config: SimpleNamespace
) -> Tuple[Optional[str], Optional[str]]:
    """OCR a remote PDF URL to markdown; returns (md_path, timestamp)."""
    markdown_path: Optional[str] = None
    timestamp_basename: Optional[str] = None
    doc_images_dir: Optional[str] = None
    try:
        api_key = config.LLM.MISTRAL_API_KEY
        if not api_key:
            logger.error("Mistral API key missing.")
            return None, None
        client = Mistral(api_key=api_key)

        timestamp_basename, markdown_filename = generate_pdf_raw_timestamp_name()
        markdown_path = os.path.join(output_folder, markdown_filename)
        doc_images_dir = os.path.join(output_folder, timestamp_basename)
        os.makedirs(doc_images_dir, exist_ok=True)

        logger.info(f"Processing PDF: {pdf_url}")
        ocr_response = client.ocr.process(
            model=config.LLM.OCR_MODEL,
            document={"type": "document_url", "document_url": pdf_url},
            include_image_base64=True,
        )
        markdown_content = get_combined_markdown(ocr_response, doc_images_dir)

        with open(markdown_path, "w", encoding="utf-8") as file:
            file.write(markdown_content)

        logger.info(f"PDF -> Raw MD success: {markdown_path}")
        return markdown_path, timestamp_basename

    except Exception as e:
        logger.error(f"Error converting PDF {pdf_url} -> MD: {e}", exc_info=True)
        if markdown_path and os.path.exists(markdown_path):
            try:
                os.remove(markdown_path)
            except OSError:
                pass
        if doc_images_dir and os.path.exists(doc_images_dir):
            try:
                shutil.rmtree(doc_images_dir)
            except OSError:
                pass
        return None, None


def pdf_file_to_markdown(
    pdf_path: str, output_folder: str, config: SimpleNamespace
) -> Tuple[Optional[str], Optional[str]]:
    """OCR a local PDF file to markdown; returns (md_path, timestamp)."""
    markdown_path: Optional[str] = None
    timestamp_basename: Optional[str] = None
    doc_images_dir: Optional[str] = None
    try:
        api_key = config.LLM.MISTRAL_API_KEY
        if not api_key:
            logger.error("Mistral API key missing.")
            return None, None
        client = Mistral(api_key=api_key)

        timestamp_basename, markdown_filename = generate_pdf_raw_timestamp_name()
        markdown_path = os.path.join(output_folder, markdown_filename)
        doc_images_dir = os.path.join(output_folder, timestamp_basename)
        os.makedirs(doc_images_dir, exist_ok=True)

        logger.info(f"Processing local PDF: {pdf_path}")
        # Upload local file to Mistral and use returned file_id (per SDK docs)
        try:
            uploaded = client.files.upload(
                file={
                    "file_name": os.path.basename(pdf_path),
                    "content": open(pdf_path, "rb"),
                }
            )
            file_id = getattr(uploaded, "id", None)
            if not file_id:
                raise RuntimeError("Mistral file upload did not return a file_id.")
            ocr_response = client.ocr.process(
                model=config.LLM.OCR_MODEL,
                document={"type": "file", "file_id": file_id},
                include_image_base64=True,
            )

            markdown_content = get_combined_markdown(ocr_response, doc_images_dir)

            with open(markdown_path, "w", encoding="utf-8") as file:
                file.write(markdown_content)

            logger.info(f"Local PDF -> Raw MD success: {markdown_path}")
            return markdown_path, timestamp_basename
        except Exception as ocr_err:
            logger.warning(
                f"Mistral OCR failed for local PDF, falling back to PyPDF text extraction: {ocr_err}"
            )
            # Fallback: simple text extraction via PyPDF
            try:
                reader = PdfReader(pdf_path)
                pieces = []
                for page in reader.pages:
                    pieces.append(page.extract_text() or "")
                text = "\n\n".join(pieces).strip()
                header = f"# Source URL: \n# Imported From: Local PDF\n# Original File: {os.path.basename(pdf_path)}\n# Timestamp: {timestamp_basename}\n\n---\n\n"
                with open(markdown_path, "w", encoding="utf-8") as file:
                    file.write(header + text)
                logger.info(
                    f"Local PDF -> Raw MD success via PyPDF fallback: {markdown_path}"
                )
                return markdown_path, timestamp_basename
            except Exception as pypdf_err:
                logger.error(f"PyPDF fallback failed: {pypdf_err}")
                raise

    except Exception as e:
        logger.error(f"Error converting local PDF {pdf_path} -> MD: {e}", exc_info=True)
        if markdown_path and os.path.exists(markdown_path):
            try:
                os.remove(markdown_path)
            except OSError:
                pass
        if doc_images_dir and os.path.exists(doc_images_dir):
            try:
                shutil.rmtree(doc_images_dir)
            except OSError:
                pass
        return None, None


def save_base64_image(
    base64_str: str, output_dir: str, img_name: str = None
) -> Optional[str]:
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError as e:
            logger.error(f"Failed create dir {output_dir}: {e}")
            return None
    if img_name is None:
        img_name = f"image_{uuid.uuid4().hex[:8]}.png"
    elif not any(
        img_name.lower().endswith(ext)
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    ):
        img_name += ".png"
    if "," in base64_str:
        try:
            _, encoded_data = base64_str.split(",", 1)
            base64_str = encoded_data
        except ValueError:
            logger.warning(f"Comma found but couldn't split prefix {img_name}.")
    img_path = os.path.join(output_dir, img_name)
    try:
        img_data = base64.b64decode(base64_str, validate=True)
        with open(img_path, "wb") as img_file:
            img_file.write(img_data)
        logger.debug(f"Saved image {img_name} to {img_path}")
        return img_path
    except Exception as e:
        logger.error(f"Image save error {img_name}: {e}")
        return None


def get_combined_markdown(ocr_response, doc_images_dir: str) -> str:
    markdowns = []
    page_num = 1
    if not hasattr(ocr_response, "pages") or not ocr_response.pages:
        logger.warning("OCR response missing pages.")
        return ""
    for page in ocr_response.pages:
        image_data = {}
        if hasattr(page, "images") and page.images:
            for img in page.images:
                if hasattr(img, "id") and hasattr(img, "image_base64"):
                    image_data[img.id] = img.image_base64
        page_markdown = getattr(page, "markdown", "")
        # Replace placeholders with saved image links
        for img_id, b64 in image_data.items():
            filename = f"{img_id}.png"
            saved = save_base64_image(b64, doc_images_dir, filename)
            if saved:
                page_markdown = page_markdown.replace(
                    f"![{img_id}]({img_id})", f"![{img_id}]({filename})"
                )
        markdowns.append(page_markdown)
        page_num += 1
    return "\n\n---\n\n".join(markdowns)
