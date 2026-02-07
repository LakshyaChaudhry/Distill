"""Vault Scanner — discovers Obsidian note titles from a vault directory."""
from __future__ import annotations

import re
from pathlib import Path


def scan_vault(vault_path: str) -> list[str]:
    """Recursively scan an Obsidian vault for .md note titles.

    Args:
        vault_path: Path to the root of the Obsidian vault.

    Returns:
        Sorted list of note titles (filenames without .md extension).

    Raises:
        FileNotFoundError: If vault_path does not exist.
        NotADirectoryError: If vault_path is not a directory.
    """
    root = Path(vault_path)
    if not root.exists():
        raise FileNotFoundError(f"Vault path not found: {vault_path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Vault path is not a directory: {vault_path}")

    titles: list[str] = []
    for md_file in root.rglob("*.md"):
        # Skip hidden files/directories (.obsidian/, .trash/, etc.)
        if any(part.startswith(".") for part in md_file.relative_to(root).parts):
            continue
        title = md_file.stem
        if title:
            titles.append(title)

    titles.sort()
    print(f"[vault] Scanned {len(titles)} notes from {vault_path}")
    return titles


def filter_vault_notes(
    titles: list[str],
    paper_keywords: list[str],
    paper_title: str,
    max_notes: int = 500,
) -> list[str]:
    """Pre-filter vault notes for relevance to reduce LLM token usage.

    Keeps notes whose title shares at least one meaningful token
    with the paper's keywords or title.

    Args:
        titles: All vault note titles.
        paper_keywords: Keywords from paper metadata (tags, section names).
        paper_title: The paper's title string.
        max_notes: Maximum number of notes to return.

    Returns:
        Filtered and capped list of note titles.
    """
    if len(titles) <= max_notes:
        return titles

    # Build keyword set from tags and title
    keywords: set[str] = set()
    for kw in paper_keywords:
        keywords.update(kw.lower().replace("-", " ").split())
    for word in re.split(r"\W+", paper_title.lower()):
        if len(word) > 2:
            keywords.add(word)

    # Score each title by keyword overlap
    scored: list[tuple[int, str]] = []
    for title in titles:
        title_words = set(re.split(r"\W+", title.lower()))
        overlap = len(title_words & keywords)
        scored.append((overlap, title))

    # Sort by overlap descending, then alphabetically
    scored.sort(key=lambda x: (-x[0], x[1]))
    filtered = [title for _, title in scored[:max_notes]]

    print(f"[vault] Filtered {len(titles)} notes down to {len(filtered)} relevant notes")
    return filtered
