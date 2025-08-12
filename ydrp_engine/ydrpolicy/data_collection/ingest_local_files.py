import csv
import logging
import os
from typing import Optional, Tuple

from ydrpolicy.data_collection.config import config as data_config
from pypdf import PdfReader
import pymupdf  # PyMuPDF
from ydrpolicy.data_collection.processors.pdf_processor import (
    extract_pdf_markdown_with_links,
)


logger = logging.getLogger(__name__)


def _normalize_text_no_blank_lines(text: str) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return "\n".join(lines)


def _get_import_pdf_path(filename_or_path: str) -> Optional[str]:
    if os.path.isfile(filename_or_path):
        return filename_or_path
    candidate = os.path.join(data_config.PATHS.PDF_DIR, filename_or_path)
    return candidate if os.path.isfile(candidate) else None


def _write_processed_txt(pdf_path: str, processed_dir: str) -> Optional[str]:
    os.makedirs(processed_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    txt_path = os.path.join(processed_dir, f"{base}.txt")
    try:
        # Prefer PyMuPDF to preserve hyperlinks; serialize links inline as [text](url)
        text_with_links = extract_pdf_markdown_with_links(pdf_path)
        normalized = _normalize_text_no_blank_lines(text_with_links)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(normalized)
        return txt_path
    except Exception as mupdf_err:
        logger.warning(f"PyMuPDF failed for '{pdf_path}', falling back to PyPDF: {mupdf_err}")
        try:
            reader = PdfReader(pdf_path)
            pieces = [page.extract_text() or "" for page in reader.pages]
            normalized = _normalize_text_no_blank_lines("\n".join(pieces))
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(normalized)
            return txt_path
        except Exception as e:
            logger.error(f"Failed to extract text from PDF '{pdf_path}': {e}")
            return None


def ingest_single_file(
    file: str,
    source_url: Optional[str],
    origin: str = "download",
    overwrite: bool = False,
) -> bool:
    if origin not in {"download", "webpage"}:
        logger.error("origin must be one of: 'download', 'webpage'")
        return False
    pdf_path = _get_import_pdf_path(file)
    if not pdf_path:
        logger.error(f"PDF not found (expected in IMPORT_DIR): {file}")
        return False
    processed_dir = data_config.PATHS.TXT_DIR
    os.makedirs(processed_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    txt_path = os.path.join(processed_dir, f"{base}.txt")
    if os.path.exists(txt_path) and not overwrite:
        logger.info(f"Processed TXT exists and overwrite=False. Skipping: {txt_path}")
        return True
    return _write_processed_txt(pdf_path=pdf_path, processed_dir=processed_dir) is not None


def ingest_from_csv(csv_path: str) -> Tuple[int, int]:
    if not os.path.isfile(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return 0, 0
    success = 0
    failed = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"filename", "url", "origin"}
        if not required.issubset({(c or "").strip() for c in (reader.fieldnames or [])}):
            logger.error("CSV must contain headers: filename,url,origin [overwrite]")
            return 0, 0
        for row in reader:
            filename = (row.get("filename") or "").strip()
            url = (row.get("url") or "").strip()
            origin = (row.get("origin") or "download").strip().lower()
            overwrite_flag = (row.get("overwrite") or "").strip().lower() in {"yes", "true", "1", "y"}
            if ingest_single_file(file=filename, source_url=url, origin=origin, overwrite=overwrite_flag):
                success += 1
            else:
                failed += 1
    logger.info(f"CSV ingestion complete. Success: {success}, Failed: {failed}")
    return success, failed


