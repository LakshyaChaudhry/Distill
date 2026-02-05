# Distill

CLI agent that parses ArXiv papers and produces structured data for downstream processing into Obsidian markdown notes.

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env` and fill in your credentials:

```
AZURE_DOC_INTEL_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOC_INTEL_KEY=your-key-here
```

## Usage

Parse a paper from ArXiv:

```bash
python -m distill.cli https://arxiv.org/abs/2301.12345 --output ./test_output
```

Parse a local PDF:

```bash
python -m distill.cli ./paper.pdf --output ./test_output
```

## Output

The parser returns a `PaperData` object containing:

- **metadata** — title, authors, date, arxiv_id, source_url
- **sections** — dict mapping section names to their text content
- **full_text** — concatenated raw text as fallback
- **figures** — extracted images saved to `{output}/figures/`
- **tables** — markdown-formatted tables

Results from Azure Document Intelligence are cached as `{pdf_path}.cache.json` to avoid redundant API calls during development.
