"""Writer — renders structured paper data into Obsidian markdown notes."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from distill.tools.parse import PaperData
from distill.tools.digest import PaperDigest
from distill.tools.gaps import ResearchGaps

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def sanitize_filename(title: str) -> str:
    """Convert a paper title to a valid, clean filename.

    'Neural Codec Language Models are Zero-Shot Text to Speech Synthesizers'
    → 'neural-codec-language-models-are-zero-shot-text-to-speech'
    """
    name = title.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"[\s]+", "-", name).strip("-")
    name = re.sub(r"-+", "-", name)
    # Truncate to 60 chars on a word boundary
    if len(name) > 60:
        name = name[:60].rsplit("-", 1)[0]
    return name.strip("-")


def copy_figures(
    figures: list[dict],
    output_dir: Path,
    figures_subdir: str = "attachments",
) -> list[dict]:
    """Copy extracted figures to the output attachments directory.

    Args:
        figures: List of figure dicts from PaperData (with 'path' key).
        output_dir: Root output directory.
        figures_subdir: Subdirectory name for figures.

    Returns:
        Updated figures list with 'filename' key added.
    """
    target_dir = output_dir / figures_subdir
    os.makedirs(target_dir, exist_ok=True)

    updated = []
    for fig in figures:
        src = Path(fig["path"])
        if not src.exists():
            print(f"[writer] Figure not found, skipping: {src}")
            continue

        dest = target_dir / src.name
        shutil.copy2(src, dest)

        updated.append({
            **fig,
            "filename": src.name,
        })

    return updated


def render_note(
    paper_data: PaperData,
    digest: PaperDigest,
    gaps: ResearchGaps | None,
    output_dir: Path | str,
    figures_subdir: str = "attachments",
    linked_concepts: list[str] | None = None,
) -> Path:
    """Render the final Obsidian markdown note.

    Args:
        paper_data: Parsed paper data.
        digest: Structured paper digest.
        gaps: Research gaps (or None if skipped).
        output_dir: Directory to write the note and figures.
        figures_subdir: Subdirectory for figure attachments.

    Returns:
        Path to the created markdown file.
    """
    output_dir = Path(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Copy figures to attachments
    figures = copy_figures(paper_data.figures, output_dir, figures_subdir)
    print(f"[writer] Copied {len(figures)} figures to {output_dir / figures_subdir}")

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["wikilink"] = lambda x: f"[[{x}]]"
    template = env.get_template("note.md.j2")

    # Render
    rendered = template.render(
        paper_data=paper_data,
        digest=digest,
        gaps=gaps,
        figures=figures,
        linked_concepts=linked_concepts,
    )

    # Write file
    filename = sanitize_filename(digest.title) + ".md"
    note_path = output_dir / filename
    note_path.write_text(rendered)

    print(f"[writer] Note written to: {note_path}")
    return note_path
