"""Gaps Agent — identifies research gaps and extension opportunities."""
from __future__ import annotations

from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

from distill.agents.digest import PaperDigest, prepare_content, _parse_llm_json

load_dotenv()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ResearchGaps:
    """Research gaps and extension opportunities for a paper."""

    open_questions: list[str]  # 3-5 unanswered questions
    extension_ideas: list[str]  # 2-4 concrete project ideas
    scaling_considerations: str  # what breaks at scale
    methodological_gaps: list[str]  # 1-3 weaknesses


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a research advisor helping identify opportunities for follow-up work \
on an academic paper. Think critically and constructively.

Return a single JSON object with exactly these keys:
- "open_questions": array of 3-5 strings — important unanswered questions \
raised by this work
- "extension_ideas": array of 2-4 strings — concrete, actionable project ideas \
that extend this work. Be specific: not "do more experiments" but "apply X method \
to Y domain to test Z hypothesis"
- "scaling_considerations": string — what happens when this approach is applied \
at larger scale, to different domains, or with more data? What assumptions break?
- "methodological_gaps": array of 1-3 strings — weaknesses in the methodology, \
missing baselines, questionable assumptions, or evaluation gaps. Be constructive.

Return ONLY the JSON object. No markdown fencing, no explanation."""


def _build_user_prompt(
    digest: PaperDigest,
    paper_sections: dict[str, str] | None = None,
) -> str:
    """Build the user message for the gaps LLM call."""
    parts = [
        f"Paper: {digest.title}",
        f"Authors: {', '.join(digest.authors)}",
        f"Venue: {digest.venue}",
        "",
        f"Key Contribution: {digest.key_contribution}",
        "",
        f"Methodology: {digest.methodology}",
        "",
        f"Core Results: {digest.core_results}",
        "",
        f"Known Limitations: {digest.limitations}",
        "",
        f"Tags: {', '.join(digest.tags)}",
    ]

    if paper_sections:
        content = prepare_content(paper_sections, "", max_chars=100_000)
        if content.strip():
            parts.append("")
            parts.append("--- RAW PAPER SECTIONS (for deeper analysis) ---")
            parts.append(content)

    return "\n".join(parts)


def identify_gaps(
    digest: PaperDigest,
    paper_sections: dict[str, str] | None = None,
) -> ResearchGaps:
    """Identify research gaps and extension opportunities.

    Args:
        digest: PaperDigest from the digest agent.
        paper_sections: Optional raw sections for deeper analysis.

    Returns:
        ResearchGaps with all fields populated.

    Raises:
        ValueError: If LLM returns unparseable JSON.
        anthropic.APIError: If the API call fails.
    """
    user_prompt = _build_user_prompt(digest, paper_sections)
    print(f"[gaps] Prompt prepared: {len(user_prompt)} chars")

    print("[gaps] Calling Claude for research gaps analysis...")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text
    print(f"[gaps] Received response: {len(raw_text)} chars")

    data = _parse_llm_json(raw_text)

    gaps = ResearchGaps(
        open_questions=data.get("open_questions", []),
        extension_ideas=data.get("extension_ideas", []),
        scaling_considerations=data.get("scaling_considerations", ""),
        methodological_gaps=data.get("methodological_gaps", []),
    )

    print(
        f"[gaps] Analysis complete: {len(gaps.open_questions)} questions, "
        f"{len(gaps.extension_ideas)} ideas"
    )
    return gaps
