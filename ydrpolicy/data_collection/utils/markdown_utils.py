import re
from typing import List


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """
    Sanitize a string to be safe for filenames/directory names.

    Args:
        name: Raw name string.
        max_len: Maximum length of the resulting filename.

    Returns:
        A sanitized filename string containing only word chars, hyphens, and underscores.
    """
    if not name:
        return "untitled_policy"
    sanitized = re.sub(r"[^\w\-]+", "_", name)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_-")
    sanitized = sanitized[:max_len]
    return sanitized or "untitled_policy"


def filter_markdown_for_txt(markdown_lines: List[str]) -> str:
    """
    Filter markdown lines to exclude common navigation/menu items for TXT output.

    Expects a list of lines with original line endings.

    Args:
        markdown_lines: List of markdown lines.

    Returns:
        A single string containing filtered text content.
    """
    filtered_lines: List[str] = []
    skip_prefixes = (
        "* ",
        "+ ",
        "- ",
        "[",
        "# Content from URL:",
        "# Final Accessed URL:",
        "# Retrieved at:",
    )
    link_only_pattern = re.compile(r"^\s*\[.*\]\(.*\)\s*$")

    for line in markdown_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(skip_prefixes):
            continue
        if link_only_pattern.match(stripped):
            continue
        if stripped in ("MENU", "Back to Top"):
            continue
        if stripped.count("/") > 2 and stripped.startswith("/"):
            continue
        filtered_lines.append(line)

    return "".join(filtered_lines)


