"""Digest Agent — produces a structured summary of an academic paper."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

from distill.tools.parse import PaperData

load_dotenv()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class PaperDigest:
    """Structured digest of a research paper."""

    title: str
    authors: list[str]
    date: str
    venue: str  # conference/journal if detectable, else "ArXiv"
    arxiv_id: str | None
    tags: list[str]  # 3-5 topic tags
    key_contribution: str  # 1-2 sentences
    methodology: str  # 1 paragraph
    core_results: str  # 1 paragraph
    limitations: str  # acknowledged + unacknowledged
    connections: list[str]  # for Obsidian linking


# ---------------------------------------------------------------------------
# Content preparation
# ---------------------------------------------------------------------------

PRIORITY_SECTIONS = [
    "Abstract",
    "Introduction",
    "Methods",
    "Methodology",
    "Method",
    "Approach",
    "Model",
    "Results",
    "Experiments",
    "Evaluation",
    "Discussion",
    "Conclusion",
    "Conclusions",
    "Related Work",
    "Background",
]


def _fuzzy_match_section(section_name: str, priority: str) -> bool:
    """Check if a section name matches a priority keyword.

    Handles numbered sections like '3. Methodology' or '2 Methods and Data'.
    """
    cleaned = re.sub(r"^[\d\.\:\s]+", "", section_name).strip().lower()
    return priority.lower() in cleaned


def prepare_content(
    sections: dict[str, str],
    full_text: str,
    max_chars: int = 200_000,
) -> str:
    """Prepare paper content for LLM consumption.

    Prioritizes important sections. Falls back to full_text if the sections
    dict is sparse (< 3 real sections after filtering out 'Title').

    Args:
        sections: Section name -> text content from PaperData.
        full_text: Concatenated raw text fallback.
        max_chars: Maximum character budget.

    Returns:
        Formatted string ready for the LLM prompt.
    """
    real_sections = {k: v for k, v in sections.items() if k != "Title"}

    # Sparse sections — use full_text
    if len(real_sections) < 3:
        content = full_text[:max_chars]
        if len(full_text) > max_chars:
            content += "\n\n[Content truncated due to length]"
        return content

    # Build content from sections in priority order
    parts: list[str] = []
    used: set[str] = set()
    char_count = 0

    # First pass: priority sections
    for priority in PRIORITY_SECTIONS:
        for name, text in real_sections.items():
            if name in used:
                continue
            if _fuzzy_match_section(name, priority):
                header = f"## {name}\n\n"
                entry = header + text.strip() + "\n\n"
                if char_count + len(entry) > max_chars:
                    remaining = max_chars - char_count - len(header) - 50
                    if remaining > 200:
                        entry = header + text[:remaining].strip() + "\n\n[Truncated]\n\n"
                        parts.append(entry)
                        char_count += len(entry)
                    break
                parts.append(entry)
                char_count += len(entry)
                used.add(name)

    # Second pass: remaining sections
    for name, text in real_sections.items():
        if name in used:
            continue
        header = f"## {name}\n\n"
        entry = header + text.strip() + "\n\n"
        if char_count + len(entry) > max_chars:
            remaining = max_chars - char_count - len(header) - 50
            if remaining > 200:
                entry = header + text[:remaining].strip() + "\n\n[Truncated]\n\n"
                parts.append(entry)
            break
        parts.append(entry)
        char_count += len(entry)
        used.add(name)

    return "".join(parts)


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code fences.

    Raises:
        ValueError: If JSON cannot be extracted or parsed.
    """
    stripped = text.strip()

    # Try direct parse
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Failed to parse JSON from LLM response. Raw response:\n{text[:500]}"
    )


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a research paper analysis assistant. Given the extracted content of an \
academic paper, produce a structured analysis.

Be concise and precise. Write for a researcher who wants to quickly understand \
what this paper contributes without reading the whole thing.

Return a single JSON object with exactly these keys:
- "tags": array of 3-5 topic tags (lowercase, hyphenated, e.g. ["text-to-speech", "neural-codec", "zero-shot-learning"])
- "key_contribution": string, 1-2 sentences on the ONE novel contribution
- "methodology": string, 1 concise paragraph summarizing the approach
- "core_results": string, 1 paragraph on key findings with specific metrics if available
- "limitations": string, both acknowledged limitations and any you identify
- "connections": array of 3-7 strings — related concepts, methods, or research areas \
formatted as potential note titles (e.g. "Transformer Architecture", "Self-Supervised Learning")
- "venue": string, the conference or journal if detectable from the text, otherwise "ArXiv"

Return ONLY the JSON object. No markdown fencing, no explanation."""


def _build_user_prompt(paper_data: PaperData, content: str) -> str:
    """Build the user message for the digest LLM call."""
    meta = paper_data.metadata
    parts = [
        f"Paper Title: {meta.get('title', 'Unknown')}",
        f"Authors: {meta.get('authors', 'Unknown')}",
    ]
    if meta.get("arxiv_id"):
        parts.append(f"ArXiv ID: {meta['arxiv_id']}")
    if meta.get("date"):
        parts.append(f"Date: {meta['date']}")

    parts.append("")
    parts.append("--- PAPER CONTENT ---")
    parts.append(content)

    return "\n".join(parts)


def digest_paper(paper_data: PaperData) -> PaperDigest:
    """Generate a structured digest of a paper using Claude.

    Args:
        paper_data: Parsed paper data from the parser agent.

    Returns:
        PaperDigest with all fields populated.

    Raises:
        ValueError: If LLM returns unparseable JSON.
        anthropic.APIError: If the API call fails.
    """
    print("[digest] Preparing content...")
    content = prepare_content(paper_data.sections, paper_data.full_text)
    print(f"[digest] Content prepared: {len(content)} chars")

    user_prompt = _build_user_prompt(paper_data, content)

    print("[digest] Calling Claude for paper digest...")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text
    print(f"[digest] Received response: {len(raw_text)} chars")

    data = _parse_llm_json(raw_text)

    # Metadata from parser (ground truth), analysis from LLM
    meta = paper_data.metadata
    authors_raw = meta.get("authors", "Unknown")
    if isinstance(authors_raw, str):
        authors_list = re.split(r",|;|\band\b", authors_raw)
        authors_list = [a.strip() for a in authors_list if a.strip()]
    else:
        authors_list = authors_raw

    digest = PaperDigest(
        title=meta.get("title", "Unknown"),
        authors=authors_list,
        date=meta.get("date") or "Unknown",
        venue=data.get("venue", "ArXiv"),
        arxiv_id=meta.get("arxiv_id"),
        tags=data.get("tags", []),
        key_contribution=data.get("key_contribution", ""),
        methodology=data.get("methodology", ""),
        core_results=data.get("core_results", ""),
        limitations=data.get("limitations", ""),
        connections=data.get("connections", []),
    )

    print(f"[digest] Digest complete: {digest.title}")
    return digest
