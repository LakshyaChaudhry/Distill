"""CLI entry point for the Distill agent."""
from __future__ import annotations

import argparse

from distill.agent import run

DEFAULT_OUTPUT = "/Users/lakshyachaudhry/desktop/mind/03_papers"
DEFAULT_VAULT = "/Users/lakshyachaudhry/desktop/mind/02_concepts"


def main():
    parser = argparse.ArgumentParser(
        prog="distill",
        description="Distill an academic paper into a structured Obsidian note.",
    )
    parser.add_argument(
        "source",
        help="ArXiv URL (e.g. https://arxiv.org/abs/2301.12345) or local PDF path",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output directory for the note and figures (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--vault", "-V",
        default=DEFAULT_VAULT,
        help=f"Obsidian vault path for concept linking (default: {DEFAULT_VAULT})",
    )
    parser.add_argument(
        "--no-vault",
        action="store_true",
        help="Skip vault scanning and concept linking",
    )

    args = parser.parse_args()

    vault_path = None if args.no_vault else args.vault
    run(args.source, args.output, vault_path=vault_path)


if __name__ == "__main__":
    main()
