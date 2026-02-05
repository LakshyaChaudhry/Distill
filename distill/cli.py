"""CLI entry point for the Distill parser."""
from __future__ import annotations

import argparse
import sys

from distill.parser import parse_paper


def main():
    parser = argparse.ArgumentParser(
        description="Parse an academic paper from ArXiv URL or local PDF."
    )
    parser.add_argument(
        "source",
        help="ArXiv URL (e.g. https://arxiv.org/abs/2301.12345) or local PDF path",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="./output",
        help="Output directory for figures and results (default: ./output)",
    )

    args = parser.parse_args()

    try:
        paper = parse_paper(args.source, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    print("\n" + "=" * 60)
    print("PAPER SUMMARY")
    print("=" * 60)
    print(f"Title:    {paper.metadata.get('title', 'Unknown')}")
    print(f"Authors:  {paper.metadata.get('authors', 'Unknown')}")
    print(f"ArXiv ID: {paper.metadata.get('arxiv_id', 'N/A')}")
    print(f"Date:     {paper.metadata.get('date', 'N/A')}")
    print(f"Sections: {len(paper.sections)}")
    for name in paper.sections:
        preview = paper.sections[name][:80].replace("\n", " ")
        print(f"  - {name}: {preview}...")
    print(f"Figures:  {len(paper.figures)}")
    for fig in paper.figures:
        caption = fig.get("caption") or "No caption"
        caption_preview = caption[:60].replace("\n", " ")
        print(f"  - p.{fig['page_number']}: {caption_preview}")
    print(f"Tables:   {len(paper.tables)}")
    print(f"Source:   {paper.source}")
    print("=" * 60)


if __name__ == "__main__":
    main()
