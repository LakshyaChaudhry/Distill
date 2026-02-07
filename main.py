"""End-to-end test script for the Distill pipeline."""
from pathlib import Path

from distill.parser import parse_paper
from distill.agents.digest import digest_paper
from distill.agents.gaps import identify_gaps
from distill.writer import render_note

SOURCE = "https://arxiv.org/abs/2301.02111"
OUTPUT_DIR = Path("./test_output")


def main():
    print(f"Parsing: {SOURCE}")
    paper = parse_paper(SOURCE, str(OUTPUT_DIR))

    print(f"\nGenerating digest...")
    digest = digest_paper(paper)

    print(f"\nIdentifying research gaps...")
    gaps = identify_gaps(digest, paper.sections)

    print(f"\nWriting Obsidian note...")
    note_path = render_note(paper, digest, gaps, OUTPUT_DIR)

    print(f"\nDone! Note written to: {note_path}")


if __name__ == "__main__":
    main()
