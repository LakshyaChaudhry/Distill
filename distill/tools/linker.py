"""Concept Linker — embeds [[wikilinks]] into digest text using LLM reasoning."""
from __future__ import annotations

import anthropic
from dotenv import load_dotenv

from distill.tools.digest import PaperDigest, _parse_llm_json

load_dotenv()


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a knowledge graph linker for an Obsidian vault. Given a paper digest \
and a list of existing vault note titles, your job is to embed [[wikilinks]] \
into the digest text where concepts naturally appear.

Rules:
1. Only link to notes that exist in the provided vault list — do NOT invent links.
2. Use the EXACT note title with [[double brackets]]: e.g. [[Transformer Architecture]].
3. Link each concept at most ONCE per field (first natural occurrence only).
4. Insert links inline within the existing prose — do NOT alter the meaning or wording.
5. Only link when the text genuinely discusses that concept, not superficial mentions.
6. If a concept is a close match (e.g. vault has "Attention" and text says \
"attention mechanism"), link it as [[Attention]] at the appropriate point.
7. Preserve all original text — only add [[ and ]] around matching concept names.

Return a JSON object with exactly these keys:
- "key_contribution": string with [[wikilinks]] embedded
- "methodology": string with [[wikilinks]] embedded
- "core_results": string with [[wikilinks]] embedded
- "limitations": string with [[wikilinks]] embedded
- "linked_concepts": array of strings — the vault note titles you actually linked

Return ONLY the JSON object. No markdown fencing, no explanation."""


def _build_user_prompt(digest: PaperDigest, vault_notes: list[str]) -> str:
    """Build the user prompt for the linker LLM call."""
    parts = [
        f"Paper: {digest.title}",
        f"Tags: {', '.join(digest.tags)}",
        "",
        "--- EXISTING VAULT NOTES ---",
        "\n".join(f"- {title}" for title in vault_notes),
        "",
        "--- DIGEST TEXT FIELDS TO LINK ---",
        "",
        "key_contribution:",
        digest.key_contribution,
        "",
        "methodology:",
        digest.methodology,
        "",
        "core_results:",
        digest.core_results,
        "",
        "limitations:",
        digest.limitations,
    ]
    return "\n".join(parts)


def link_concepts(
    digest: PaperDigest,
    vault_notes: list[str],
) -> tuple[PaperDigest, list[str]]:
    """Embed [[wikilinks]] into digest text fields using LLM reasoning.

    Args:
        digest: The PaperDigest to enhance with links.
        vault_notes: List of vault note titles to match against.

    Returns:
        Tuple of (modified PaperDigest, list of linked concept names).

    Raises:
        ValueError: If LLM returns unparseable JSON.
        anthropic.APIError: If the API call fails.
    """
    if not vault_notes:
        print("[linker] No vault notes provided, skipping linking")
        return digest, []

    user_prompt = _build_user_prompt(digest, vault_notes)
    print(f"[linker] Prompt prepared: {len(user_prompt)} chars, {len(vault_notes)} vault notes")

    print("[linker] Calling Claude for concept linking...")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text
    print(f"[linker] Received response: {len(raw_text)} chars")

    data = _parse_llm_json(raw_text)

    # Build a new PaperDigest with linked text fields
    linked_digest = PaperDigest(
        title=digest.title,
        authors=digest.authors,
        date=digest.date,
        venue=digest.venue,
        arxiv_id=digest.arxiv_id,
        tags=digest.tags,
        key_contribution=data.get("key_contribution", digest.key_contribution),
        methodology=data.get("methodology", digest.methodology),
        core_results=data.get("core_results", digest.core_results),
        limitations=data.get("limitations", digest.limitations),
        connections=digest.connections,
    )

    linked_concepts = data.get("linked_concepts", [])
    print(f"[linker] Linked {len(linked_concepts)} concepts: {linked_concepts}")

    return linked_digest, linked_concepts
