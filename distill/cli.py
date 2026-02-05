"""CLI entry point for the Distill pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from distill.parser import parse_paper


def main():
    parser = argparse.ArgumentParser(
        description="Parse an academic paper and generate AI-powered analysis."
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
    parser.add_argument(
        "--skip-gaps",
        action="store_true",
        help="Skip the research gaps analysis step",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print full JSON output for digest and gaps",
    )

    args = parser.parse_args()

    # --- Step 1: Parse paper ---
    try:
        paper = parse_paper(args.source, args.output)
    except Exception as e:
        print(f"Error parsing paper: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("PAPER PARSED")
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

    # --- Step 2: Digest ---
    try:
        from distill.agents.digest import digest_paper
    except ImportError as e:
        print(f"\nSkipping digest: {e}", file=sys.stderr)
        print("Install the anthropic package: pip3 install anthropic", file=sys.stderr)
        sys.exit(0)

    print("\n" + "=" * 60)
    print("GENERATING DIGEST...")
    print("=" * 60)

    try:
        digest = digest_paper(paper)
    except Exception as e:
        print(f"Error generating digest: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("PAPER DIGEST")
    print("=" * 60)
    print(f"Title:        {digest.title}")
    print(f"Authors:      {', '.join(digest.authors)}")
    print(f"Date:         {digest.date}")
    print(f"Venue:        {digest.venue}")
    print(f"ArXiv ID:     {digest.arxiv_id or 'N/A'}")
    print(f"Tags:         {', '.join(digest.tags)}")
    print(f"\nKey Contribution:")
    print(f"  {digest.key_contribution}")
    print(f"\nMethodology:")
    print(f"  {digest.methodology}")
    print(f"\nCore Results:")
    print(f"  {digest.core_results}")
    print(f"\nLimitations:")
    print(f"  {digest.limitations}")
    print(f"\nConnections:  {', '.join(digest.connections)}")

    if args.verbose:
        print("\n--- DIGEST JSON ---")
        print(json.dumps(asdict(digest), indent=2))

    # --- Step 3: Gaps (unless --skip-gaps) ---
    if not args.skip_gaps:
        try:
            from distill.agents.gaps import identify_gaps
        except ImportError as e:
            print(f"\nSkipping gaps: {e}", file=sys.stderr)
            sys.exit(0)

        print("\n" + "=" * 60)
        print("ANALYZING RESEARCH GAPS...")
        print("=" * 60)

        try:
            gaps = identify_gaps(digest, paper.sections)
        except Exception as e:
            print(f"Error analyzing gaps: {e}", file=sys.stderr)
            sys.exit(1)

        print("\n" + "=" * 60)
        print("RESEARCH GAPS")
        print("=" * 60)
        print("\nOpen Questions:")
        for i, q in enumerate(gaps.open_questions, 1):
            print(f"  {i}. {q}")
        print("\nExtension Ideas:")
        for i, idea in enumerate(gaps.extension_ideas, 1):
            print(f"  {i}. {idea}")
        print(f"\nScaling Considerations:")
        print(f"  {gaps.scaling_considerations}")
        print("\nMethodological Gaps:")
        for i, gap in enumerate(gaps.methodological_gaps, 1):
            print(f"  {i}. {gap}")

        if args.verbose:
            print("\n--- GAPS JSON ---")
            print(json.dumps(asdict(gaps), indent=2))

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
