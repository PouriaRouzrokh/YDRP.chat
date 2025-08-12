# ydrpolicy/data_collection/processors/pdf_processor.py

import os
import base64
import uuid
import logging
import datetime
import shutil
from types import SimpleNamespace
from typing import Tuple, Optional

from pypdf import PdfReader
import pymupdf  # PyMuPDF

logger = logging.getLogger(__name__)


def generate_pdf_raw_timestamp_name() -> Tuple[str, str]:
    now = datetime.datetime.now()
    timestamp_basename = now.strftime("%Y%m%d%H%M%S%f")
    markdown_filename = f"{timestamp_basename}.md"
    return timestamp_basename, markdown_filename


def pdf_url_to_markdown(
    pdf_url: str, output_folder: str, config: SimpleNamespace
) -> Tuple[Optional[str], Optional[str]]:
    """Deprecated: remote URL OCR removed; use local ingestion with PyPDF."""
    logger.warning("pdf_url_to_markdown is deprecated. Returning (None, None).")
    return None, None


def pdf_file_to_markdown(
    pdf_path: str, output_folder: str, config: SimpleNamespace
) -> Tuple[Optional[str], Optional[str]]:
    """Extract text from a local PDF to markdown via PyPDF; returns (md_path, timestamp)."""
    markdown_path: Optional[str] = None
    timestamp_basename: Optional[str] = None
    doc_images_dir: Optional[str] = None
    try:
        timestamp_basename, markdown_filename = generate_pdf_raw_timestamp_name()
        markdown_path = os.path.join(output_folder, markdown_filename)
        logger.info(f"Processing local PDF via PyMuPDF with hyperlink preservation: {pdf_path}")
        try:
            text = extract_pdf_markdown_with_links(pdf_path)
            with open(markdown_path, "w", encoding="utf-8") as file:
                # Do not include any header here; ingestion step will add a unified header.
                file.write(text)
            logger.info(f"Local PDF -> MD via PyMuPDF success: {markdown_path}")
            return markdown_path, timestamp_basename
        except Exception as mupdf_err:
            logger.error(f"PyMuPDF extraction failed, falling back to PyPDF: {mupdf_err}")
            try:
                reader = PdfReader(pdf_path)
                pieces = []
                for page in reader.pages:
                    pieces.append(page.extract_text() or "")
                text = "\n\n".join(pieces).strip()
                with open(markdown_path, "w", encoding="utf-8") as file:
                    file.write(text)
                logger.info(f"Local PDF -> MD via PyPDF fallback success: {markdown_path}")
                return markdown_path, timestamp_basename
            except Exception as pypdf_err:
                logger.error(f"PyPDF fallback extraction failed: {pypdf_err}")
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


def extract_pdf_markdown_with_links(pdf_path: str) -> str:
    """
    Extracts text from PDF and preserves hyperlinks as Markdown links.

    Strategy:
    - Use PyMuPDF to get page words in reading order and page links with their rectangles.
    - For each line, wrap contiguous words that intersect a link rectangle as [text](url).
    - Non-linked text is preserved verbatim.

    Returns:
        Markdown-flavored text with [text](URL) where applicable.
    """
    try:
        lines_out = []
        with pymupdf.open(pdf_path) as doc:
            for page in doc:
                try:
                    link_rects = []
                    for lnk in page.get_links() or []:
                        uri = lnk.get("uri")
                        rect = lnk.get("from") or lnk.get("rect")
                        if not uri or not rect:
                            continue
                        try:
                            link_rects.append((pymupdf.Rect(rect), uri))
                        except Exception:
                            # Skip malformed rectangles
                            continue

                    words = page.get_text("words", sort=True) or []
                    if not words:
                        # Try OCR directly if no words are detected (likely scanned page)
                        try:
                            tp = page.get_textpage_ocr(languages="eng")
                            ocr_text = page.get_text("text", textpage=tp) or ""
                            for raw_line in (ocr_text.splitlines() if ocr_text else []):
                                lines_out.append(raw_line)
                            lines_out.append("")
                            continue
                        except Exception:
                            # Fall back to simple text if OCR unavailable
                            text_plain = page.get_text("text") or ""
                            for raw_line in (text_plain.splitlines() if text_plain else []):
                                lines_out.append(raw_line)
                            lines_out.append("")
                            continue

                    # Reconstruct lines based on block and line indices
                    def flush_line(parts):
                        if not parts:
                            return ""
                        segments = []
                        buf_words = []
                        buf_url = None
                        for token, url in parts:
                            if url == buf_url:
                                buf_words.append(token)
                            else:
                                if buf_words:
                                    seg_text = " ".join(buf_words)
                                    if buf_url:
                                        segments.append(f"[{seg_text}]({buf_url})")
                                    else:
                                        segments.append(seg_text)
                                buf_words = [token]
                                buf_url = url
                        if buf_words:
                            seg_text = " ".join(buf_words)
                            if buf_url:
                                segments.append(f"[{seg_text}]({buf_url})")
                            else:
                                segments.append(seg_text)
                        return " ".join(segments)

                    current_key = None  # (block_no, line_no)
                    current_parts = []  # list[(token, url)]

                    for x0, y0, x1, y1, token, block_no, line_no, word_no in words:
                        key = (block_no, line_no)
                        if current_key is None:
                            current_key = key
                        if key != current_key:
                            lines_out.append(flush_line(current_parts))
                            current_parts = []
                            current_key = key

                        word_rect = pymupdf.Rect(x0, y0, x1, y1)
                        url_for_word = None
                        for rect, uri in link_rects:
                            if rect.intersects(word_rect):
                                url_for_word = uri
                                break
                        current_parts.append((token, url_for_word))

                    if current_parts:
                        lines_out.append(flush_line(current_parts))

                    # Heuristic check for gibberish text due to font encoding; if so, OCR the page
                    try:
                        page_text_candidate = "\n".join(lines_out[-(len(current_parts) + 1) :]) if current_parts else "\n".join(lines_out[-1:])
                    except Exception:
                        page_text_candidate = ""

                    def _looks_gibberish(text: str) -> bool:
                        if not text or len(text) < 40:
                            return False
                        letters = sum(ch.isalpha() for ch in text)
                        digits = sum(ch.isdigit() for ch in text)
                        spaces = text.count(" ") + text.count("\n") + text.count("\t")
                        total = len(text)
                        alpha_ratio = letters / max(total, 1)
                        space_ratio = spaces / max(total, 1)
                        # Many PDFs with broken encoding show very low alpha ratio and odd spacing
                        return alpha_ratio < 0.35 and space_ratio < 0.35

                    if _looks_gibberish("\n".join(lines_out[-200:])):
                        try:
                            tp = page.get_textpage_ocr(languages="eng")
                            ocr_text = page.get_text("text", textpage=tp) or ""
                            # Replace the last page's lines (best-effort): append OCR text as new page section
                            lines_out.append(ocr_text)
                        except Exception:
                            pass

                    # Page separator blank line
                    lines_out.append("")
                except Exception as page_err:
                    logger.warning(f"Failed to extract page {page.number}: {page_err}")
                    text_plain = page.get_text("text") or ""
                    if text_plain:
                        lines_out.extend(text_plain.splitlines())
                        lines_out.append("")

        result = "\n".join(lines_out).strip()
        return result
    except Exception as e:
        logger.error(f"PyMuPDF hyperlink-aware extraction failed for '{pdf_path}': {e}")
        raise
