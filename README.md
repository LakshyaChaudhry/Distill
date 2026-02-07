# Distill

An agentic CLI tool that reads academic papers and produces structured Obsidian markdown notes — complete with inline `[[wikilinks]]` to your existing vault concepts.

Distill uses Claude's tool-calling API to orchestrate a multi-step pipeline: parsing PDFs with Azure Document Intelligence, generating structured analysis with an LLM, scanning your Obsidian vault for relevant concepts, and rendering everything into a linked markdown note.

## Architecture

### Agentic Tool-Calling Loop

Distill is built around an **agentic loop** — rather than a hardcoded pipeline, a Claude model decides which tools to call and in what order based on the system prompt and intermediate results.

```
┌─────────────────────────────────────────────────────────┐
│                    Distill Agent                        │
│                  (Claude Sonnet)                        │
│                                                         │
│  System Prompt: "You have 6 tools. Use them in order."  │
│                                                         │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐              │
│  │ Decide  │──>│  Call   │──>│ Process │──┐            │
│  │  next   │   │  tool   │   │ result  │  │            │
│  │  tool   │   │         │   │         │  │            │
│  └─────────┘   └─────────┘   └─────────┘  │            │
│       ^                                    │            │
│       └────────────────────────────────────┘            │
│                  (loop until done)                      │
└─────────────────────────────────────────────────────────┘
```

### Pipeline Flow

When a vault path is provided, the agent runs 6 tools. Without a vault, it skips `scan_vault` and `link_concepts` (4 tools).

```
                    ┌──────────────┐
                    │  ArXiv URL   │
                    │  or PDF path │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ parse_paper  │  Azure Document Intelligence
                    │              │  + PyMuPDF figure extraction
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │      scan_vault         │  Recursively scan Obsidian
              │   (if vault provided)   │  vault for .md note titles
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │ digest_paper │  Claude Sonnet generates
                    │              │  structured analysis (JSON)
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │    link_concepts        │  Claude Sonnet identifies
              │   (if vault provided)   │  vault concepts in digest,
              │                         │  embeds [[wikilinks]] inline
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │identify_gaps │  Claude Sonnet finds research
                    │              │  gaps and extension ideas
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  write_note  │  Jinja2 renders Obsidian
                    │              │  markdown with frontmatter
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   .md note   │
                    │  in vault    │
                    └──────────────┘
```

### Vault Concept Linking (Decision-Making)

This is where the agent does real reasoning — not just following a script.

```
┌──────────────────────┐     ┌───────────────────────────────┐
│   Your Vault Notes   │     │     Paper Digest Fields       │
│                      │     │                               │
│ - Attention          │     │ key_contribution: "VALL-E     │
│ - Transformer        │     │   treats TTS as conditional   │
│ - Zero-Shot Learning │────>│   language modeling..."       │
│ - Neural Codec       │     │                               │
│ - Autoregressive     │     │ methodology: "Uses a neural   │
│ - ...200 more notes  │     │   codec for discrete audio    │
│                      │     │   tokens with a transformer   │
└──────────────────────┘     │   decoder..."                 │
                             └───────────────┬───────────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  Claude Sonnet  │
                                    │   Reasons:      │
                                    │                 │
                                    │ "Attention" ──> │ mentioned but
                                    │   not central,  │ skip
                                    │                 │
                                    │ "Transformer"──>│ core to method,
                                    │   link it       │
                                    │                 │
                                    │ "Zero-Shot" ──> │ in the title,
                                    │   link it       │
                                    │                 │
                                    │ "Neural Codec"─>│ key concept,
                                    │   link it       │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────────────────┐
                                    │ Output:                     │
                                    │                             │
                                    │ "Uses a [[Neural Codec]]    │
                                    │  for discrete audio tokens  │
                                    │  with a [[Transformer]]     │
                                    │  decoder..."                │
                                    └─────────────────────────────┘
```

### Project Structure

```
distill/
├── __init__.py          # Package exports
├── __main__.py          # python3 -m distill entry point
├── agent.py             # Agentic loop, tool definitions, state management
├── cli.py               # CLI argument parsing
├── tools/
│   ├── parse.py         # PDF parsing (Azure Doc Intelligence + PyMuPDF)
│   ├── digest.py        # LLM-powered paper digest
│   ├── gaps.py          # LLM-powered research gap analysis
│   ├── vault.py         # Obsidian vault scanner
│   ├── linker.py        # LLM-powered concept linking
│   └── write.py         # Jinja2 note renderer
└── templates/
    └── note.md.j2       # Obsidian markdown template
```

## Setup

### Prerequisites

- Python 3.9+
- [Azure Document Intelligence](https://azure.microsoft.com/en-us/products/ai-services/ai-document-intelligence) resource (for PDF parsing)
- [Anthropic API key](https://console.anthropic.com/) (for Claude Sonnet)

### Install

```bash
git clone https://github.com/LakshyaChaudhry/Distill.git
cd Distill
pip3 install -e .
```

### Configure

Create a `.env` file in the project root:

```
AZURE_DOC_INTEL_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOC_INTEL_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
```

## Usage

```bash
# Distill a paper (defaults to your configured vault + output dir)
python3 -m distill https://arxiv.org/abs/2301.02111

# Override output directory
python3 -m distill https://arxiv.org/abs/2301.02111 -o ./output

# Specify a vault for concept linking
python3 -m distill https://arxiv.org/abs/2301.02111 -V /path/to/vault

# Skip vault linking entirely
python3 -m distill https://arxiv.org/abs/2301.02111 --no-vault

# Local PDF
python3 -m distill ./paper.pdf
```

## Output

Distill produces an Obsidian markdown note with:

- **YAML frontmatter** — title, authors, date, venue, tags, arxiv ID
- **Key Contribution** — 1-2 sentence summary of the novel contribution
- **Methodology** — concise description of the approach
- **Core Results** — key findings with metrics
- **Figures** — extracted images embedded as `![[filename]]`
- **Limitations** — both acknowledged and identified
- **Connections** — related concepts as `[[wikilinks]]`
- **Linked Vault Concepts** — your existing notes linked inline in the text
- **Research Gaps** — open questions, extension ideas, scaling considerations

## How It Works

1. **Parse** — Azure Document Intelligence extracts text, sections, and tables from the PDF. PyMuPDF extracts figures. Results are cached to avoid repeat API calls.

2. **Scan Vault** — Recursively discovers all `.md` files in your Obsidian vault. For large vaults (500+ notes), pre-filters by keyword relevance to the paper.

3. **Digest** — Claude Sonnet reads the extracted paper content and produces a structured JSON analysis: key contribution, methodology, results, limitations, tags, and connections.

4. **Link Concepts** — Claude Sonnet receives the digest text and your vault note titles, then reasons about which concepts are genuinely discussed in the paper. It embeds `[[wikilinks]]` inline — only linking each concept once, only where it naturally appears.

5. **Identify Gaps** — Claude Sonnet analyzes the paper for research gaps: unanswered questions, extension ideas, scaling considerations, and methodological weaknesses.

6. **Write Note** — Jinja2 renders everything into a formatted Obsidian markdown note with proper frontmatter, figure embeds, and wikilinks.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| PDF Parsing | Azure Document Intelligence (prebuilt-layout) |
| Figure Extraction | PyMuPDF |
| LLM Analysis | Claude Sonnet (Anthropic API) |
| Agent Orchestration | Anthropic tool-calling API |
| Templating | Jinja2 |
| Output Format | Obsidian-flavored Markdown |
