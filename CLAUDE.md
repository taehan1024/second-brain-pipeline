# CLAUDE.md

This file provides guidance to Claude when working anywhere inside `second-brain-pipeline/`.

## Operating Principle

**Always cross-reference with the vault and memory.** Before answering research questions, reviewing code, or suggesting approaches — search the vault first, then check `memory.md` for past decisions and pitfalls. The vault contains curated research papers. `memory.md` contains accumulated learnings — proven design decisions, failed experiments, data pitfalls. Ground every response in what we already know. When we don't know enough, say so and suggest how to fill the gap.

## What This Is

`second-brain-pipeline/` is a unified research system — an Obsidian vault at the root with a Python pipeline alongside it:

- **`scripts/`** — Python scripts that download arXiv papers and convert them. Raw PDFs stored in `scripts/arxiv_pdfs/`.
- **Root-level vault folders** (`00-Inbox/`, `10-Knowledge/`, `20-Notes/`, `30-Projects/`) — Obsidian knowledge vault. Notes, metadata, and project work live here directly.


---

## Folder Structure

```
second-brain-pipeline/
├── CLAUDE.md                         # how to behave (process, rules, structure)
├── memory.md                         # what we've learned (facts, results, pitfalls)
├── README.md
├── Makefile
├── requirements.txt
├── config/
│   └── topics.yaml                  # 200+ curated search queries
├── docs/
│   └── workflow.md
├── scripts/                          # pipeline scripts + raw PDFs
│   ├── arxiv_downloader.py
│   ├── pdf_to_md.py
│   ├── tag_metadata.py
│   ├── vault_search.py
│   ├── _download_log.json           # master download registry
│   └── arxiv_pdfs/                  # downloaded PDFs by topic
│       └── {topic_slug}/
│
├── 00-Inbox/                         # landing zone
├── 10-Knowledge/                     # source material
│   ├── arxiv_mds/                   # converted markdown notes
│   │   └── {topic_slug}/
│   └── metadata/                    # one *-metadata.md per paper
├── 20-Notes/                         # my thinking: synthesis/, daily/
└── 30-Projects/                      # active work
    └── active/
```

---

## Research Focus Areas

Papers organized under `10-Knowledge/arxiv_mds/` by topic:

- **Quantitative finance**: `market_microstructure`, `factor_model_finance`, `regime_switching`, `deep_hedging`, `option_pricing_machine_learning`
- **Statistical modeling**: `mixed_effects_model`, `state_space_model`, `survival_analysis`, `functional_data_analysis`, `bayesian_deep_learning`
- **Optimization**: `frank_wolfe_algorithm`, `nonconvex_optimization`, `sparse_estimation`
- **Machine learning**: `large_language_model`, `interpretable_machine_learning`, `neural_network`, `graph_neural_network`, `transformer_architecture`, `diffusion_model`
- **Mathematics**: `random_matrix_theory`, `tensor_decomposition`, `principal_component_analysis`, `high_dimensional_statistics`
- **RL**: `reinforcement_learning`

## Canonical Tags

`machine-learning`, `deep-learning`, `high-dim-stats`, `optimization`, `quant-finance`, `probabilistic-models`, `time-series`, `tensor-methods`, `functional-data`, `reinforcement-learning`, `causal-inference`

---

## Pipeline

### Running the scripts

```bash
# 1. Download PDFs
python3 scripts/arxiv_downloader.py
python3 scripts/arxiv_downloader.py --topic "transformers" --max 20 --min-citations 50

# 2. Convert PDFs to markdown notes
python3 scripts/pdf_to_md.py

# 3. Tag metadata cards (topic mapping + content-based enrichment)
python3 scripts/tag_metadata.py --suggest --apply

# 4. Search vault
python3 scripts/vault_search.py --tags quant-finance --min-citations 50
```

Key defaults in `scripts/arxiv_downloader.py`: `DEFAULT_MAX_PAPERS = 10`, `DEFAULT_MIN_CITATIONS = 20`, `DEFAULT_DAYS_BACK = 365`, `ARXIV_DELAY_SEC = 3.0`, `S2_DELAY_SEC = 1.5`.

### Pipeline flow

1. **`arxiv_downloader.py`** — queries arXiv XML API + Semantic Scholar for citations, downloads PDFs to `scripts/arxiv_pdfs/{topic}/`, writes metadata stubs to `10-Knowledge/metadata/` and `_download_log.json` to `scripts/`
2. **`pdf_to_md.py`** — reads PDFs from `scripts/arxiv_pdfs/{topic}/`, writes converted `.md` notes to `10-Knowledge/arxiv_mds/{topic}/`
3. **`tag_metadata.py`** — walks `10-Knowledge/metadata/` and enriches tags on metadata cards
4. **`vault_search.py`** — searches metadata and full paper MDs, identifies knowledge gaps

### Path constants (all scripts use relative paths from `__file__`)

| Constant | Resolves to |
|---|---|
| `PDF_PATH` | `scripts/arxiv_pdfs/` — PDFs live here |
| `NOTES_PATH` | `10-Knowledge/arxiv_mds/` — converted markdown notes |
| `METADATA_DIR` | `10-Knowledge/metadata/` — metadata cards |
| `LOG_PATH` | `scripts/_download_log.json` — master download registry |

Papers already in `_download_log.json` are skipped — safe to re-run.

**External APIs:** `export.arxiv.org/api/query` (XML, no auth), `api.semanticscholar.org/graph/v1/paper/arXiv:{id}` (JSON, no auth)

---

## vault_search.py

```bash
# Search
scripts/vault_search.py --tags quant-finance time-series --min-citations 50
scripts/vault_search.py --query "factor model" --top 10
scripts/vault_search.py --query "cross-sectional return" --deep        # full paper MD search

# Knowledge gaps
scripts/vault_search.py --gaps stock-prediction                        # what research is missing?
scripts/vault_search.py --gaps recommender-system --deep               # deep scan
scripts/vault_search.py --gaps-init "anomaly detection for network security"  # auto-generate map

# Project-aware
scripts/vault_search.py --project stock-prediction                     # auto-loads project tags

# Vault health
scripts/vault_search.py --audit                                        # tag coverage + data quality

# Claude Code integration
scripts/vault_search.py --tags quant-finance --prompt "extract features" --top 5

# Export
scripts/vault_search.py --tags finance --export results.md
scripts/vault_search.py --tags finance --json
```

`--gaps` reports ✅ strong / 🟡 weak / ❌ missing areas and outputs exact `arxiv_downloader.py` commands to fill gaps. `--gaps-init` auto-generates a KNOWLEDGE_MAP entry from a problem description — scans vault, clusters papers by tag, extracts keywords from abstracts, outputs copy-paste-ready Python dict. KNOWLEDGE_MAP defined for: `stock-prediction`, `baseball-analytics`, `crypto-investing`, `recommender-system`.

## tag_metadata.py

```bash
scripts/tag_metadata.py --suggest --apply      # Suggest tags from abstract content, With --suggest, write suggestions to files
scripts/tag_metadata.py --audit                # Report tag health without changing files
scripts/tag_metadata.py --synonyms             # Check for synonym/split tag issues

```

---

## Project Workflow

When starting or continuing a project in 30-Projects/:

1. **Map the problem.** `scripts/vault_search.py --gaps-init "your problem"` auto-generates a knowledge map. Review, paste into KNOWLEDGE_MAP.
2. **Check gaps.** `scripts/vault_search.py --gaps {problem}` to see what research is missing. Fill gaps before building.
3. **Search → Read → Synthesize → Build.** `vault_search.py` filters papers (free) → Claude Code deep-reads 3-5 papers (not 50) → write synthesis note answering ONE design question → Claude Code generates code FROM the synthesis note.
3. **Synthesis note before code.** Never generate code directly from papers. Write a note in `20-Notes/synthesis/` first. This is the highest-ROI artifact.
4. **Start with the dumbest baseline.** Simplest model on simplest target. Failure tells you whether the problem is target, features, or model.
5. **Log everything in index.md.** Every experiment gets a row in the results table + key findings.
6. **Terminal for running, Claude Code for thinking.** Don't burn tokens watching scripts execute.

### Reinforcement knowledge loop

```
--gaps-init generates map → --gaps identifies holes → download → convert → tag → --gaps again → holes shrink → synthesize → build → log
```

Every project makes the vault stronger for all future projects.

---

## Vault Note Format

Every full paper note under `10-Knowledge/arxiv_mds/{topic}/`:

- **No YAML frontmatter** in full notes
- `#` (h1) for the arXiv ID line only; `##` (h2) for title; `###` (h3) for numbered sections
- Filenames are kebab-case slugs derived from the paper title
- Images stored in `{filename}_images/` subdirectory alongside the note

## Metadata Card Format (`10-Knowledge/metadata/`)

Pipeline-generated index cards — one per paper. The **only** files in the vault that use YAML frontmatter. Contains: tags, arxiv_id, categories, published date, citations, authors, pdf filename, truncated abstract.

---

## RAG Instructions

When looking for papers or research context, follow this order:

1. Run `vault_search.py` to filter by tags/citations/keywords — this is free
2. Check `10-Knowledge/metadata/` — read metadata cards for abstracts
3. Only then read full notes under `10-Knowledge/arxiv_mds/{topic}/` if deeper content is needed
4. Read 3-5 papers max per question — don't try to read everything

Cite source filename in responses.

---

## Jarvis Mode

**Every question or task should be cross-referenced with the vault.** Don't answer from general knowledge when the vault has specific, curated research. The vault is the primary source of truth.

### Answering Questions

When asked a question about a technique, method, or concept:

1. **Check memory.md first.** A design decision or pitfall may already be documented from a past project.
2. **Search the vault.** Run `scripts/vault_search.py --query "{topic}" --top 10` (or `--deep` for full text).
3. **Read the top matches.** Check metadata cards, then full papers if needed.
4. **Check synthesis notes.** Look in `20-Notes/synthesis/` — a design decision may already be made.
5. **Answer grounded in vault + memory.** Cite specific papers, notes, and memory entries. Say which source supports each claim.
6. **Flag gaps.** If the vault has weak or no coverage, say so: *"Your vault has 2 papers on X but none on Y. Run: `scripts/vault_search.py --gaps-init 'Y'` to check."*

### Analyzing External Code / Repos

When asked to validate, review, or improve code from GitHub or elsewhere:

1. **Read the code.** Identify: what model/technique, what features, what target, what loss function, what evaluation method.
2. **Check memory.md.** We may have already tried this technique — check design decisions and model benchmarks.
3. **Search the vault for each technique.** Run `scripts/vault_search.py --query "{technique}" --deep --top 10` for each major technique found in the code.
4. **Cross-reference.** Compare the code's approach against papers in the vault and synthesis notes in `20-Notes/synthesis/`
5. **Check gaps.** If the vault has weak coverage on a technique the code uses, flag it and suggest downloads.
6. **Suggest improvements grounded in research.** Every suggestion must trace to a paper, synthesis note, or memory entry. No ungrounded opinions.

Response pattern:
```
"This repo uses [technique X]. Your vault has [N] papers on X.
The top-cited one [[paper-name]] suggests [alternative Y].
Your synthesis note [[note-name]] already decided [Z] for [reason].
memory.md notes: [relevant past result or pitfall].
Recommendation: [concrete change with code]."
```

### Learning When Knowledge is Missing

When the vault doesn't have enough to answer well:

1. Don't guess. Say: *"The vault has limited coverage on this topic."*
2. Run `scripts/vault_search.py --gaps-init "{topic}"` to generate a knowledge map.
3. Show the suggested download commands.
4. After papers are downloaded and tagged, re-answer the question.

### What NOT to do

- Don't answer research questions from general knowledge without checking the vault and memory.md
- Don't read 50 papers — read 3-5 of the highest-cited matches
- Don't suggest code changes without tracing them to a specific paper or synthesis note
- Don't skip vault_search.py and jump straight to reading random papers

### Updating memory.md

After completing an experiment, project iteration, or discovering a pitfall, append the learning to the appropriate section in `memory.md`. Every entry should include: what was learned, the evidence, and which project/date it came from.

---

## Obsidian Configuration

Sync managed via Obsidian Sync. Configuration in `.obsidian/` (root of vault). Graph view is the primary navigation surface, configured to show tags, attachments, and orphaned notes with `linkDistance: 250`.
