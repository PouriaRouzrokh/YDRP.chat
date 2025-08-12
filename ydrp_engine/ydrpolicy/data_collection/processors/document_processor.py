"""
Module for handling document downloads and conversions.
"""

import logging
import os
import re
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

# Document processing libraries
import markdownify
import requests
from docx import Document

# Local imports (updated path)
from pypdf import PdfReader
import pymupdf  # PyMuPDF
from ydrpolicy.data_collection.processors.pdf_processor import (
    extract_pdf_markdown_with_links,
)

# Set up logging
logger = logging.getLogger(__name__)


def download_document(url: str, output_dir: str, config: SimpleNamespace) -> str:
    """
    Download a document from a URL and save it to the output directory.

    Args:
        url: URL of the document to download
        output_dir: Directory to save the document

    Returns:
        Path to the downloaded document
    """
    os.makedirs(output_dir, exist_ok=True)

    # Create a filename from the URL
    parsed_url = urllib.parse.urlparse(url)

    # For Yale document repository URLs with UUIDs
    if "files-profile.medicine.yale.edu/documents/" in url:
        # Extract UUID as filename
        match = re.search(r"/documents/([a-f0-9-]+)", parsed_url.path)
        if match:
            filename = f"yale_doc_{match.group(1)}.pdf"  # Assume PDF for Yale documents
        else:
            filename = f"yale_doc_{hash(url) % 10000}.pdf"
    else:
        # Normal filename extraction
        filename = os.path.basename(parsed_url.path)

        # If filename is empty or doesn't have an extension, create one
        if not filename or "." not in filename:
            # Generate a filename based on the URL hash
            filename = f"document_{hash(url) % 10000}{Path(parsed_url.path).suffix}"
            if "." not in filename:
                # If still no extension, default to .pdf (common for dynamic URLs)
                filename += ".pdf"

    file_path = os.path.join(output_dir, filename)

    try:
        # Download the file
        logger.info(f"Downloading document from {url}")

        # Set up request headers to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        response = requests.get(
            url, stream=True, timeout=config.CRAWLER.REQUEST_TIMEOUT, headers=headers
        )
        response.raise_for_status()

        # Check content type to confirm it's a document
        content_type = response.headers.get("Content-Type", "").lower()
        is_document = (
            "pdf" in content_type
            or "msword" in content_type
            or "application/vnd.openxmlformats" in content_type
            or "application/vnd.ms-excel" in content_type
            or "application/octet-stream" in content_type
        )

        if not is_document:
            logger.warning(
                f"Content type '{content_type}' may not be a document for {url}"
            )
            # Continue anyway - some servers don't set correct content types

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Document downloaded successfully to {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        return ""


def convert_to_markdown(file_path: str, url: str, config: SimpleNamespace) -> str:
    """
    Convert a document to markdown based on its file type.

    Args:
        file_path: Path to the document
        url: Original URL of the document (for OCR fallback)

    Returns:
        Document content in markdown format
    """
    file_ext = Path(file_path).suffix.lower()

    try:
        # Handle different file types
        if file_ext in [".pdf"]:
            # Convert PDF to simple markdown using PyPDF (no external OCR)
            return convert_pdf_to_markdown(file_path)
        elif file_ext in [".doc", ".docx"]:
            return convert_docx_to_markdown(file_path)
        else:
            logger.warning(f"Unsupported file type: {file_ext}")
            return f"# Unsupported Document\n\nFile: {os.path.basename(file_path)}\nURL: {url}\n\nThis document type is not supported for conversion."

    except Exception as e:
        logger.error(f"Error converting document to markdown: {str(e)}")
        return ""


def convert_pdf_to_markdown(file_path: str) -> str:
    """
    Convert a PDF document to simple markdown-like text using PyPDF only.

    Args:
        file_path: Path to the PDF document

    Returns:
        PDF content as plain text separated by newlines (no blank lines).
    """
    try:
        # Prefer PyMuPDF to preserve hyperlinks, falling back to PyPDF
        text_joined = extract_pdf_markdown_with_links(file_path)
        title = os.path.basename(file_path)
        return f"# {title}\n\n{text_joined}"
    except Exception as mupdf_err:
        logger.warning(f"PyMuPDF failed to convert PDF preserving links, fallback to PyPDF: {mupdf_err}")
        try:
            reader = PdfReader(file_path)
            pieces = []
            for page in reader.pages:
                text = page.extract_text() or ""
                lines = [ln for ln in text.splitlines() if ln.strip()]
                pieces.append("\n".join(lines))
            text_joined = "\n".join(pieces).strip()
            title = os.path.basename(file_path)
            return f"# {title}\n\n{text_joined}"
        except Exception as e:
            logger.error(f"Error converting PDF via PyPDF fallback: {str(e)}")
            return f"# Error Processing PDF\n\nFile: {os.path.basename(file_path)}\n\nError: {str(e)}"


def convert_docx_to_markdown(file_path: str) -> str:
    """
    Convert a DOCX document to markdown using python-docx.

    Args:
        file_path: Path to the DOCX document

    Returns:
        DOCX content in markdown format
    """
    try:
        doc = Document(file_path)
        text = ""

        # Extract document title or use filename
        title = os.path.basename(file_path)

        # Process each paragraph
        for para in doc.paragraphs:
            if para.text.strip():
                # Handle headings based on style
                style_name = para.style.name.lower()
                if "heading" in style_name:
                    heading_level = "".join(filter(str.isdigit, style_name)) or "1"
                    text += f"{'#' * int(heading_level)} {para.text}\n\n"
                else:
                    text += f"{para.text}\n\n"

        # Process tables if any
        for table in doc.tables:
            text += "\n| "
            # Add headers
            for cell in table.rows[0].cells:
                text += cell.text + " | "
            text += "\n| "

            # Add separator
            for _ in table.rows[0].cells:
                text += "--- | "
            text += "\n"

            # Add data rows (skip header)
            for row in table.rows[1:]:
                text += "| "
                for cell in row.cells:
                    text += cell.text + " | "
                text += "\n"
            text += "\n"

        return f"# {title}\n\n{text}"

    except Exception as e:
        logger.error(f"Error converting DOCX to markdown: {str(e)}")
        return f"# Error Processing DOCX\n\nFile: {os.path.basename(file_path)}\n\nError: {str(e)}"


def html_to_markdown(html_content: str) -> str:
    """
    Convert HTML content to markdown using markdownify.

    Args:
        html_content: HTML content to convert

    Returns:
        Content in markdown format
    """
    try:
        return markdownify.markdownify(html_content, heading_style="ATX")
    except Exception as e:
        logger.error(f"Error converting HTML to markdown: {str(e)}")
        return ""
