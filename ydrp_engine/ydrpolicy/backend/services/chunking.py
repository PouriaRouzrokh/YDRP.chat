import re
import logging
from typing import List, Optional

from ydrpolicy.backend.config import config

# Initialize logger
logger = logging.getLogger(__name__)


def chunk_text(
    text: str, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None
) -> List[str]:
    """
    Split text into chunks using a recursive character-based approach.

    This chunking strategy attempts to split at logical boundaries (paragraphs,
    sentences), falling back to character boundaries when necessary.

    Args:
        text: The text to split into chunks
        chunk_size: Maximum size of each chunk (in characters)
        chunk_overlap: Overlap between chunks (in characters)

    Returns:
        List of text chunks
    """
    # Use default values from config if not provided
    if chunk_size is None:
        chunk_size = config.RAG.CHUNK_SIZE

    if chunk_overlap is None:
        chunk_overlap = config.RAG.CHUNK_OVERLAP

    logger.debug(
        f"Chunking text of length {len(text)} with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}"
    )

    # If text is already small enough, return it as a single chunk
    if len(text) <= chunk_size:
        return [text]

    chunks = []

    # First try to split by double newlines (paragraphs)
    paragraphs = re.split(r"\n\s*\n", text)

    # If we have multiple paragraphs and some are too large
    if len(paragraphs) > 1 and any(len(p) > chunk_size for p in paragraphs):
        # Some paragraphs need further splitting
        current_chunk = ""

        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk size
            if len(current_chunk) + len(paragraph) + 2 > chunk_size:
                # If we already have content in the current chunk, add it to chunks
                if current_chunk:
                    chunks.append(current_chunk)

                # If paragraph is too large on its own, recursively split it
                if len(paragraph) > chunk_size:
                    # Recursively split the paragraph
                    paragraph_chunks = chunk_text(paragraph, chunk_size, chunk_overlap)
                    chunks.extend(paragraph_chunks)

                    # Start a new chunk with overlap from the last paragraph chunk
                    if paragraph_chunks and chunk_overlap > 0:
                        overlap_text = paragraph_chunks[-1][-chunk_overlap:]
                        current_chunk = overlap_text
                    else:
                        current_chunk = ""
                else:
                    # Paragraph fits as its own chunk
                    chunks.append(paragraph)

                    # Start a new chunk with overlap
                    if chunk_overlap > 0:
                        current_chunk = (
                            paragraph[-chunk_overlap:]
                            if len(paragraph) > chunk_overlap
                            else paragraph
                        )
                    else:
                        current_chunk = ""
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        # Add the last chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)

    # If paragraphs approach didn't work well, try sentences
    elif len(paragraphs) == 1 or all(len(p) <= chunk_size for p in paragraphs):
        # Split by sentences
        sentence_pattern = r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s"
        sentences = re.split(sentence_pattern, text)

        current_chunk = ""

        for sentence in sentences:
            # Clean up the sentence
            sentence = sentence.strip()
            if not sentence:
                continue

            # If adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) + 1 > chunk_size:
                # Add current chunk to chunks list
                if current_chunk:
                    chunks.append(current_chunk)

                # If sentence is too large, split by character
                if len(sentence) > chunk_size:
                    # Split the sentence into smaller pieces
                    for i in range(0, len(sentence), chunk_size - chunk_overlap):
                        chunks.append(sentence[i : i + chunk_size])

                    # Start a new chunk with overlap from the last piece
                    if chunk_overlap > 0:
                        overlap_text = sentence[
                            -(
                                len(sentence) % (chunk_size - chunk_overlap)
                                or (chunk_size - chunk_overlap)
                            ) :
                        ]
                        current_chunk = (
                            overlap_text
                            if len(overlap_text) <= chunk_overlap
                            else overlap_text[-chunk_overlap:]
                        )
                    else:
                        current_chunk = ""
                else:
                    # Sentence fits as its own chunk
                    chunks.append(sentence)

                    # Start a new chunk with overlap
                    if chunk_overlap > 0:
                        current_chunk = (
                            sentence[-chunk_overlap:]
                            if len(sentence) > chunk_overlap
                            else sentence
                        )
                    else:
                        current_chunk = ""
            else:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        # Add the last chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)

    # If we still don't have any chunks, fall back to simple character-based chunking
    if not chunks:
        logger.warning("Falling back to character-based chunking")
        for i in range(0, len(text), chunk_size - chunk_overlap):
            chunks.append(text[i : i + chunk_size])

    logger.debug(f"Text split into {len(chunks)} chunks")
    return chunks


def chunk_markdown(
    markdown_text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[str]:
    """
    Split markdown text into chunks, trying to preserve structure.

    This special version of chunking attempts to split at markdown headings
    and other logical boundaries first.

    Args:
        markdown_text: The markdown text to split
        chunk_size: Maximum size of each chunk (in characters)
        chunk_overlap: Overlap between chunks (in characters)

    Returns:
        List of markdown chunks
    """
    # Use default values from config if not provided
    if chunk_size is None:
        chunk_size = config.RAG.CHUNK_SIZE

    if chunk_overlap is None:
        chunk_overlap = config.RAG.CHUNK_OVERLAP

    logger.debug(f"Chunking markdown text of length {len(markdown_text)}")

    # If text is already small enough, return it as a single chunk
    if len(markdown_text) <= chunk_size:
        return [markdown_text]

    chunks = []

    # First try to split by headings (# Title)
    heading_pattern = r"(^|\n)#{1,6}\s+[^\n]+"
    headings = re.finditer(heading_pattern, markdown_text)

    # Get the positions of all headings
    heading_positions = [match.start() for match in headings]

    # If we have headings, use them as chunk boundaries
    if heading_positions:
        logger.debug(f"Found {len(heading_positions)} headings in markdown text")

        # Add start of document as a position
        all_positions = [0] + heading_positions

        # Process each section (from one heading to the next)
        for i in range(len(all_positions)):
            start = all_positions[i]
            # End is either the next heading or the end of the document
            end = (
                all_positions[i + 1]
                if i < len(all_positions) - 1
                else len(markdown_text)
            )

            section = markdown_text[start:end]

            # If section is small enough, add it as a chunk
            if len(section) <= chunk_size:
                chunks.append(section)
            else:
                # Otherwise, recursively chunk the section
                section_chunks = chunk_text(section, chunk_size, chunk_overlap)
                chunks.extend(section_chunks)
    else:
        # If no headings found, fall back to regular chunking
        logger.debug("No headings found in markdown, falling back to regular chunking")
        chunks = chunk_text(markdown_text, chunk_size, chunk_overlap)

    logger.debug(f"Markdown text split into {len(chunks)} chunks")
    return chunks
