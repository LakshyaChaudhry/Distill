"""Distill Agent — agentic tool-calling loop for paper analysis.

This module defines the tools, system prompt, and execution logic.
The run() function is the core agentic loop that YOU implement.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from distill.tools.parse import parse_paper
from distill.tools.digest import digest_paper
from distill.tools.gaps import identify_gaps
from distill.tools.vault import scan_vault, filter_vault_notes
from distill.tools.linker import link_concepts
from distill.tools.write import render_note

load_dotenv()

# ---------------------------------------------------------------------------
# Tool definitions (JSON schemas for the Anthropic tool_use API)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "parse_paper",
        "description": (
            "Parse an academic paper from an ArXiv URL or local PDF path. "
            "Extracts text, sections, metadata, figures, and tables using "
            "Azure Document Intelligence and PyMuPDF. Must be called first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "ArXiv URL (e.g. https://arxiv.org/abs/2301.12345) or local PDF path",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory to save extracted figures",
                },
            },
            "required": ["source", "output_dir"],
        },
    },
    {
        "name": "scan_vault",
        "description": (
            "Scan an Obsidian vault directory to discover existing note titles. "
            "Returns a list of note filenames that can be used for concept linking. "
            "Should be called after parse_paper if a vault_path is available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vault_path": {
                    "type": "string",
                    "description": "Path to the root of the Obsidian vault directory",
                },
            },
            "required": ["vault_path"],
        },
    },
    {
        "name": "digest_paper",
        "description": (
            "Generate a structured digest of the parsed paper using an LLM. "
            "Produces key contribution, methodology, results, limitations, "
            "tags, and connections. Requires parse_paper to have been called first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "link_concepts",
        "description": (
            "Embed [[wikilinks]] to existing vault notes inline within the paper "
            "digest text fields. Uses an LLM to identify where vault concepts "
            "naturally appear in the analysis text. Requires both digest_paper and "
            "scan_vault to have been called first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "identify_gaps",
        "description": (
            "Identify research gaps, open questions, extension ideas, and "
            "methodological weaknesses. Requires digest_paper to have been called first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "write_note",
        "description": (
            "Write the final Obsidian markdown note combining all analysis. "
            "Requires both digest_paper and identify_gaps to have been called first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "output_dir": {
                    "type": "string",
                    "description": "Directory to write the Obsidian note and figures",
                },
            },
            "required": ["output_dir"],
        },
    },
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def _build_system_prompt(vault_path: str | None) -> str:
    """Build the system prompt, conditionally including vault tools."""
    if vault_path:
        return """\
You are Distill, a research paper analysis agent. Your job is to take an \
academic paper and produce a structured Obsidian markdown note with links to \
existing vault concepts.

You have 6 tools available. Use them in this order:
1. parse_paper — Extract text, sections, figures, and metadata from the PDF
2. scan_vault — Scan the Obsidian vault for existing note titles
3. digest_paper — Generate a structured analysis (key contribution, methodology, results, etc.)
4. link_concepts — Embed [[wikilinks]] to vault concepts inline in the digest text
5. identify_gaps — Find research gaps, open questions, and extension ideas
6. write_note — Render everything into an Obsidian markdown note

Call each tool in sequence. After write_note completes, summarize what you created \
and list which vault concepts were linked."""
    else:
        return """\
You are Distill, a research paper analysis agent. Your job is to take an \
academic paper and produce a structured Obsidian markdown note.

You have 4 tools available. Use them in this order:
1. parse_paper — Extract text, sections, figures, and metadata from the PDF
2. digest_paper — Generate a structured analysis (key contribution, methodology, results, etc.)
3. identify_gaps — Find research gaps, open questions, and extension ideas
4. write_note — Render everything into an Obsidian markdown note

Call each tool in sequence. After write_note completes, summarize what you created."""

# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

# Stores actual Python objects between tool calls.
# Tool results sent back to Claude are JSON summaries,
# but we keep the real objects here for passing between tools.
state: dict = {}


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def execute_tool(name: str, tool_input: dict) -> str:
    """Execute a tool by name and return a string result for Claude.

    Updates the global state dict with Python objects.
    Returns a JSON string summary for the conversation.
    """
    if name == "parse_paper":
        paper = parse_paper(tool_input["source"], tool_input["output_dir"])
        state["paper"] = paper
        return json.dumps({
            "status": "success",
            "title": paper.metadata.get("title", "Unknown"),
            "sections": len(paper.sections),
            "figures": len(paper.figures),
            "tables": len(paper.tables),
        })

    elif name == "scan_vault":
        vault_path = tool_input["vault_path"]
        titles = scan_vault(vault_path)
        # Pre-filter if vault is large (>500 notes)
        if "paper" in state and len(titles) > 500:
            paper_title = state["paper"].metadata.get("title", "")
            section_keywords = list(state["paper"].sections.keys())
            pseudo_tags = [w.lower() for w in paper_title.split() if len(w) > 3]
            pseudo_tags.extend(section_keywords)
            titles = filter_vault_notes(titles, pseudo_tags, paper_title)
        state["vault_notes"] = titles
        return json.dumps({
            "status": "success",
            "note_count": len(titles),
            "sample": titles[:10],
        })

    elif name == "digest_paper":
        if "paper" not in state:
            return json.dumps({"error": "Must call parse_paper first"})
        digest = digest_paper(state["paper"])
        state["digest"] = digest
        return json.dumps({
            "status": "success",
            "title": digest.title,
            "tags": digest.tags,
            "key_contribution": digest.key_contribution[:200],
            "connections": digest.connections,
        })

    elif name == "link_concepts":
        if "digest" not in state:
            return json.dumps({"error": "Must call digest_paper first"})
        if "vault_notes" not in state:
            return json.dumps({"error": "Must call scan_vault first"})
        linked_digest, linked_concepts = link_concepts(
            state["digest"], state["vault_notes"]
        )
        state["digest"] = linked_digest
        state["linked_concepts"] = linked_concepts
        return json.dumps({
            "status": "success",
            "linked_concepts": linked_concepts,
            "count": len(linked_concepts),
        })

    elif name == "identify_gaps":
        if "digest" not in state:
            return json.dumps({"error": "Must call digest_paper first"})
        gaps = identify_gaps(state["digest"], state["paper"].sections)
        state["gaps"] = gaps
        return json.dumps({
            "status": "success",
            "open_questions": len(gaps.open_questions),
            "extension_ideas": len(gaps.extension_ideas),
            "methodological_gaps": len(gaps.methodological_gaps),
        })

    elif name == "write_note":
        if "digest" not in state:
            return json.dumps({"error": "Must call digest_paper first"})
        gaps = state.get("gaps")
        linked_concepts = state.get("linked_concepts")
        note_path = render_note(
            state["paper"], state["digest"], gaps, Path(tool_input["output_dir"]),
            linked_concepts=linked_concepts,
        )
        return json.dumps({
            "status": "success",
            "note_path": str(note_path),
        })

    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Agentic loop — YOUR TURN TO IMPLEMENT!
# ---------------------------------------------------------------------------


def run(source: str, output_dir: str, vault_path: str | None = None) -> None:
    """Run the Distill agent on a paper.

    Args:
        source: ArXiv URL or local PDF path.
        output_dir: Directory for output files.
        vault_path: Optional path to Obsidian vault for concept linking.
    """
    # Clear state for a fresh run
    state.clear()

    client = anthropic.Anthropic()

    # Build system prompt and tool list based on whether vault linking is enabled
    system_prompt = _build_system_prompt(vault_path)
    if vault_path:
        tools = TOOLS  # all 6 tools
    else:
        tools = [t for t in TOOLS if t["name"] not in ("scan_vault", "link_concepts")]

    # Build initial user message
    user_msg = f"Analyze this paper and create an Obsidian note: {source}\nOutput directory: {output_dir}"
    if vault_path:
        user_msg += f"\nObsidian vault path: {vault_path}"
    messages = [{"role": "user", "content": user_msg}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        # FIX 2: only print text blocks (tool_use blocks don't have .text)
        for block in response.content:
            if hasattr(block, "text"):
                print(block.text)

        if response.stop_reason == "end_of_turn":
            break

        # FIX 3: collect ALL tool results first, then append once
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[agent] Calling tool: {block.name}")
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,    # <-- ties result back to the tool call
                    "content": result,
                })

        # Append assistant message + tool results ONCE, outside the loop
        messages.append({"role": "assistant", "content": response.content})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            break  # No tools called — nothing more to do
