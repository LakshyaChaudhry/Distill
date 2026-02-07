"""Distill: Academic paper parsing and analysis toolkit."""

from distill.parser import PaperData, parse_paper
from distill.agents.digest import PaperDigest, digest_paper
from distill.agents.gaps import ResearchGaps, identify_gaps
from distill.writer import render_note

__all__ = [
    "PaperData",
    "parse_paper",
    "PaperDigest",
    "digest_paper",
    "ResearchGaps",
    "identify_gaps",
    "render_note",
]
