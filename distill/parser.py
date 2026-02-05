"""Distill Parser Agent — extracts structured content from academic PDFs.

Uses Azure Document Intelligence for text/layout extraction and
PyMuPDF for figure/image extraction.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass

import fitz  # PyMuPDF
import requests
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

CACHE_SUFFIX = ".cache.json"


@dataclass
class PaperData:
    """Structured representation of a parsed academic paper."""

    metadata: dict  # title, authors, date, arxiv_id, source_url
    sections: dict[str, str]  # section_name -> text content
    full_text: str  # concatenated raw text as fallback
    figures: list[dict]  # [{path, caption, page_number}, ...]
    tables: list[str]  # markdown-formatted tables
    source: str  # original URL or file path


# ---------------------------------------------------------------------------
# PDF Acquisition
# ---------------------------------------------------------------------------


def fetch_pdf(source: str) -> str:
    """Fetch a PDF from an ArXiv URL or verify a local file path.

    Args:
        source: ArXiv URL (e.g. https://arxiv.org/abs/2301.12345) or local path.

    Returns:
        Path to the PDF file on disk.
    """
    if source.startswith("http://") or source.startswith("https://"):
        url = source.replace("/abs/", "/pdf/")
        if not url.endswith(".pdf"):
            url += ".pdf"

        print(f"[fetch_pdf] Downloading from {url}")
        headers = {"User-Agent": "Distill-Parser/1.0 (academic research tool)"}
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()

        # Sanity check — ArXiv sometimes returns HTML error pages with 200
        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type and "octet-stream" not in content_type:
            raise ValueError(
                f"Expected a PDF response but got Content-Type: {content_type}. "
                "The URL may be invalid or ArXiv may be rate-limiting."
            )

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(resp.content)
        tmp.close()
        print(f"[fetch_pdf] Saved {len(resp.content)} bytes to {tmp.name}")
        return tmp.name

    # Local file
    if not os.path.exists(source):
        raise FileNotFoundError(f"Local PDF not found: {source}")
    print(f"[fetch_pdf] Using local file: {source}")
    return source


# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------


def _get_cache_path(pdf_path: str) -> str:
    return pdf_path + CACHE_SUFFIX


def _load_cache(pdf_path: str) -> dict | None:
    """Load cached parse result if it exists."""
    cache_path = _get_cache_path(pdf_path)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            print(f"[cache] Loaded cached result from {cache_path}")
            return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"[cache] Cache file corrupt, ignoring: {e}")
    return None


def _save_cache(pdf_path: str, data: dict) -> None:
    """Save parse result to cache file."""
    cache_path = _get_cache_path(pdf_path)
    try:
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[cache] Saved result to {cache_path}")
    except IOError as e:
        print(f"[cache] Failed to save cache: {e}")


# ---------------------------------------------------------------------------
# Azure Document Intelligence extraction
# ---------------------------------------------------------------------------


def _table_to_markdown(table) -> str:
    """Convert an Azure DocumentTable to a markdown-formatted string."""
    grid = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]

    for cell in table.cells:
        ri = cell.row_index
        ci = cell.column_index
        content = cell.content.replace("\n", " ").strip()
        # Fill spanned cells
        for dr in range(cell.row_span or 1):
            for dc in range(cell.column_span or 1):
                if ri + dr < table.row_count and ci + dc < table.column_count:
                    grid[ri + dr][ci + dc] = content if (dr == 0 and dc == 0) else ""

    lines = []
    for row_idx, row in enumerate(grid):
        line = "| " + " | ".join(row) + " |"
        lines.append(line)
        if row_idx == 0:
            sep = "| " + " | ".join(["---"] * table.column_count) + " |"
            lines.append(sep)

    return "\n".join(lines)


def extract_content(pdf_path: str) -> dict:
    """Extract structured content from a PDF using Azure Document Intelligence.

    Uses the prebuilt-layout model. Checks for cached results first.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dict with keys: sections, tables, full_text, raw_paragraphs.
    """
    # Check cache
    cached = _load_cache(pdf_path)
    if cached is not None:
        return cached

    # Validate credentials
    endpoint = os.environ.get("AZURE_DOC_INTEL_ENDPOINT")
    key = os.environ.get("AZURE_DOC_INTEL_KEY")
    if not endpoint or not key:
        raise EnvironmentError(
            "Missing required environment variables: AZURE_DOC_INTEL_ENDPOINT "
            "and/or AZURE_DOC_INTEL_KEY. Set them in a .env file or export them."
        )

    client = DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    print("[extract_content] Sending PDF to Azure Document Intelligence...")
    with open(pdf_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", body=f)
        result = poller.result()
    print("[extract_content] Analysis complete.")

    # --- Group paragraphs into sections ---
    sections: dict[str, str] = {}
    current_section = "Abstract"

    if result.paragraphs:
        for para in result.paragraphs:
            role = para.role
            content = para.content

            if role in ("pageHeader", "pageFooter", "pageNumber"):
                continue

            if role == "sectionHeading":
                current_section = content.strip()
                sections.setdefault(current_section, "")
                continue

            if role == "title":
                current_section = "Title"
                sections.setdefault(current_section, "")
                sections[current_section] += content + "\n"
                continue

            # Regular paragraph or footnote
            sections.setdefault(current_section, "")
            sections[current_section] += content + "\n\n"

    # --- Convert tables to markdown ---
    tables_md: list[str] = []
    if result.tables:
        for table in result.tables:
            tables_md.append(_table_to_markdown(table))

    # --- Serialize raw paragraphs for metadata extraction ---
    raw_paragraphs = [
        {"role": p.role, "content": p.content} for p in (result.paragraphs or [])
    ]

    output = {
        "sections": sections,
        "tables": tables_md,
        "full_text": result.content,
        "raw_paragraphs": raw_paragraphs,
    }

    _save_cache(pdf_path, output)
    return output


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


def extract_metadata(parsed_content: dict, source: str) -> dict:
    """Extract paper metadata from parsed content and source URL.

    Args:
        parsed_content: Dict returned by extract_content().
        source: Original source URL or file path.

    Returns:
        Dict with keys: title, authors, date, arxiv_id, source_url.
    """
    raw_paragraphs = parsed_content.get("raw_paragraphs", [])

    # --- Title ---
    title = "Unknown"
    title_idx = -1
    for i, para in enumerate(raw_paragraphs):
        if para.get("role") == "title":
            title = para["content"].strip()
            title_idx = i
            break
    if title == "Unknown":
        # Fallback: first line of full text
        full_text = parsed_content.get("full_text", "")
        if full_text:
            title = full_text.split("\n")[0].strip()

    # --- Authors (best-effort heuristic) ---
    # Collect paragraphs between title and first sectionHeading or "Abstract"
    authors = "Unknown"
    if title_idx >= 0:
        author_parts = []
        for para in raw_paragraphs[title_idx + 1 :]:
            role = para.get("role")
            content = para.get("content", "").strip()
            if role == "sectionHeading":
                break
            if content.lower().startswith("abstract"):
                break
            if role in ("pageHeader", "pageFooter", "pageNumber"):
                continue
            if content:
                author_parts.append(content)
        if author_parts:
            authors = " ".join(author_parts)

    # --- ArXiv ID ---
    arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", source)
    arxiv_id = arxiv_match.group(1) if arxiv_match else None

    # --- Date (from ArXiv ID: first 4 digits = YYMM) ---
    date = None
    if arxiv_id:
        yymm = arxiv_id[:4]
        try:
            year = 2000 + int(yymm[:2])
            month = int(yymm[2:4])
            date = f"{year}-{month:02d}"
        except (ValueError, IndexError):
            pass

    return {
        "title": title,
        "authors": authors,
        "date": date,
        "arxiv_id": arxiv_id,
        "source_url": source,
    }


# ---------------------------------------------------------------------------
# Figure extraction (PyMuPDF)
# ---------------------------------------------------------------------------


def _detect_caption(page) -> str | None:
    """Find a figure caption on the given page.

    Looks for text blocks starting with 'Figure' or 'Fig.'.
    Returns the first match, or None.
    """
    try:
        blocks = page.get_text("blocks")
        for block in blocks:
            if block[6] == 0:  # text block (not image block)
                text = block[4].strip()
                if text.lower().startswith("figure") or text.lower().startswith("fig."):
                    return text
    except Exception:
        pass
    return None


def extract_figures(pdf_path: str, output_dir: str) -> list[dict]:
    """Extract embedded images from a PDF using PyMuPDF.

    Filters small images (< 10KB or < 100x100). Attempts to detect captions.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save extracted images.

    Returns:
        List of dicts with keys: path, caption, page_number.
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    paper_id = os.path.splitext(os.path.basename(pdf_path))[0]

    figures: list[dict] = []
    fig_counter = 0
    seen_xrefs: set[int] = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images(full=True)

        for img_info in images:
            xref = img_info[0]

            # Skip duplicates (same image referenced on multiple pages)
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                img_data = doc.extract_image(xref)
            except Exception as e:
                print(
                    f"[figures] Failed to extract image xref={xref} "
                    f"on page {page_num + 1}: {e}"
                )
                continue

            width = img_data.get("width", 0)
            height = img_data.get("height", 0)
            image_bytes = img_data.get("image", b"")

            # Filter small images
            if len(image_bytes) < 10240:  # < 10 KB
                continue
            if width < 100 or height < 100:
                continue

            fig_counter += 1
            ext = img_data.get("ext", "png")
            filename = f"{paper_id}_fig{fig_counter}.{ext}"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            caption = _detect_caption(page)

            figures.append(
                {
                    "path": filepath,
                    "caption": caption,
                    "page_number": page_num + 1,
                }
            )

            print(
                f"[figures] Saved {filename} ({width}x{height}) from page {page_num + 1}"
            )

    doc.close()
    return figures


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def parse_paper(source: str, output_dir: str = "./output") -> PaperData:
    """Orchestrate full paper parsing pipeline.

    Steps: fetch PDF -> extract content via Azure -> extract metadata ->
    extract figures via PyMuPDF -> assemble PaperData.

    Args:
        source: ArXiv URL or local PDF path.
        output_dir: Directory to save extracted figures.

    Returns:
        PaperData with all extracted information.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Fetch PDF
    print(f"[parse_paper] Fetching PDF from: {source}")
    pdf_path = fetch_pdf(source)
    print(f"[parse_paper] PDF path: {pdf_path}")

    # Step 2: Extract content via Azure Document Intelligence
    print("[parse_paper] Extracting content with Azure Document Intelligence...")
    parsed_content = extract_content(pdf_path)

    # Step 3: Extract metadata
    print("[parse_paper] Extracting metadata...")
    metadata = extract_metadata(parsed_content, source)
    print(f"[parse_paper] Title: {metadata.get('title', 'Unknown')}")

    # Step 4: Extract figures
    print("[parse_paper] Extracting figures...")
    figures_dir = os.path.join(output_dir, "figures")
    try:
        figures = extract_figures(pdf_path, figures_dir)
    except Exception as e:
        print(f"[parse_paper] Figure extraction failed (non-fatal): {e}")
        figures = []

    # Step 5: Assemble result
    paper = PaperData(
        metadata=metadata,
        sections=parsed_content["sections"],
        full_text=parsed_content["full_text"],
        figures=figures,
        tables=parsed_content["tables"],
        source=source,
    )

    print(
        f"[parse_paper] Done. {len(paper.sections)} sections, "
        f"{len(paper.figures)} figures, {len(paper.tables)} tables."
    )

    return paper
