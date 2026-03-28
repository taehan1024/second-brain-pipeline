# second-brain-pipeline

A Python pipeline that downloads arXiv papers, converts them to markdown, tags them, and powers a searchable knowledge vault — built on top of Obsidian.

No API keys required. Both arXiv and Semantic Scholar are public APIs.

---

## What It Does

```
arXiv API + Semantic Scholar
        ↓
arxiv_downloader.py   →  PDFs + metadata stubs
        ↓
pdf_to_md.py          →  markdown notes
        ↓
tag_metadata.py       →  enriched metadata tags
        ↓
vault_search.py       →  search, gap analysis, project-aware filtering
```

Papers are filtered by citation count (default: ≥20) so you only read high-signal work.

---

## Setup

```bash
pip install -r requirements.txt
```

Configure your topics in `config/topics.yaml`. The file ships with 200+ curated search queries across ML, statistics, optimization, and quantitative finance — organized by research area.

---

## Quick Start

```bash
# Preview what would be downloaded (no files written)
make download-dry

# Download papers
make download

# Convert PDFs to markdown
make convert

# Tag metadata cards
make tag

# Search
make search QUERY="diffusion models"

# Find knowledge gaps
make gaps TOPIC="options pricing with machine learning"
```

---

## Vault Folder Layout

The scripts expect (and create) this structure relative to the repo root:

```
second-brain-pipeline/
├── scripts/arxiv_pdfs/{topic}/    # downloaded PDFs
├── 10-Knowledge/
│   ├── arxiv_mds/{topic}/         # converted markdown notes
│   └── metadata/                  # YAML metadata cards (one per paper)
```

Works well with [Obsidian](https://obsidian.md) — open the repo root as your vault.

---

## Configuration

Edit `config/topics.yaml` to customize:

- **`defaults`** — max papers per topic, min citations, days back, API rate limits
- **`categories`** — arXiv category filters (cs.LG, stat.ML, q-fin.*, etc.)
- **`topics`** — search query strings, organized by research area

```yaml
defaults:
  max_papers: 10
  min_citations: 20
  days_back: 365

topics:
  my_area:
    - "your search query here"
    - "another query"
```

---

## Scripts

| Script | What it does |
|--------|-------------|
| `arxiv_downloader.py` | Downloads PDFs + writes metadata stubs. Reads topics from `config/topics.yaml`. |
| `pdf_to_md.py` | Converts PDFs to markdown notes. |
| `tag_metadata.py` | Enriches metadata cards with content-based tags. |
| `vault_search.py` | Search by tag/query/citation, identify knowledge gaps, export results. |

See [docs/workflow.md](docs/workflow.md) for the full research workflow.

---

## CLI Reference

```bash
# Download
python3 scripts/arxiv_downloader.py --topic "diffusion models" --max 20 --min-citations 50
python3 scripts/arxiv_downloader.py --category cs.LG --days 90 --dry-run

# Search
python3 scripts/vault_search.py --query "factor model" --top 10
python3 scripts/vault_search.py --tags quant-finance --min-citations 50
python3 scripts/vault_search.py --query "returns" --deep        # full text search
python3 scripts/vault_search.py --gaps stock-prediction         # knowledge gap report
python3 scripts/vault_search.py --gaps-init "crypto investing"  # auto-generate map
python3 scripts/vault_search.py --audit                         # vault health check

# Tag
python3 scripts/tag_metadata.py --suggest --apply
python3 scripts/tag_metadata.py --audit
```

---

## Tests

```bash
make test
# or
pytest scripts/
```
