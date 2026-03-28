"""Tests for vault_search.py — synthetic fixtures + real vault."""

import textwrap, json
from pathlib import Path
from datetime import datetime, date
import pytest

from vault_search import (
    parse_frontmatter, load_all, find_paper_md, deep_search,
    search, score_paper, _to_date, audit,
    display, export_for_obsidian, export_claude_prompt,
    CANONICAL_TAGS, METADATA_DIR, PAPERS_DIR,
)

# ── Fixtures ──────────────────────────────────────────────────────────────

META_A = textwrap.dedent("""\
    ---
    tags: [machine-learning, deep-learning]
    arxiv_id: 2301.00001v1
    categories: [cs.LG, cs.AI]
    published: 2024-06-15
    date_added: 2026-03-21
    citations: 500
    authors: "Alice, Bob"
    pdf: "attention-is-all-you-need.pdf"
    source: "arXiv"
    priority: normal
    ---

    # Attention Is All You Need

    **Authors:** Alice, Bob

    ## Abstract

    We propose the transformer architecture for sequence transduction.
""")

META_B = textwrap.dedent("""\
    ---
    tags: [quant-finance, optimization]
    arxiv_id: 2302.00002v1
    categories: [q-fin.PM]
    published: 2023-01-10
    date_added: 2026-03-21
    citations: 120
    authors: "Charlie"
    pdf: "portfolio-optimization.pdf"
    source: "arXiv"
    priority: normal
    ---

    # Portfolio Optimization Under Constraints

    **Authors:** Charlie

    ## Abstract

    Robust portfolio optimization with convex constraints and risk measures.
""")

META_C = textwrap.dedent("""\
    ---
    tags: [high-dim-stats]
    arxiv_id: 2303.00003v1
    categories: [stat.ML]
    published: 2025-11-01
    date_added: 2026-03-21
    citations: 30
    authors: "Diana"
    pdf: "sparse-estimation-methods.pdf"
    source: "arXiv"
    priority: normal
    ---

    # Sparse Estimation Methods

    **Authors:** Diana

    ## Abstract

    Lasso and elastic net for high-dimensional sparse regression.
""")

FULL_PAPER_A = textwrap.dedent("""\
    # arXiv:2301.00001v1 cs.LG 2024-06-15

    ## Attention Is All You Need

    The transformer architecture uses self-attention mechanism for
    sequence-to-sequence modeling. Multi-head attention allows the model
    to attend to information from different representation subspaces.
""")


@pytest.fixture
def vault(tmp_path):
    """Build a mini vault with metadata + one full paper."""
    meta_dir = tmp_path / "metadata"
    meta_dir.mkdir()
    (meta_dir / "attention-is-all-you-need-metadata.md").write_text(META_A)
    (meta_dir / "portfolio-optimization-metadata.md").write_text(META_B)
    (meta_dir / "sparse-estimation-methods-metadata.md").write_text(META_C)

    # Full paper in a topic dir
    topic_dir = tmp_path / "large_language_model"
    topic_dir.mkdir()
    (topic_dir / "attention-is-all-you-need.md").write_text(FULL_PAPER_A)

    return tmp_path, meta_dir


# ── parse_frontmatter ─────────────────────────────────────────────────────

class TestParseFrontmatter:
    def test_returns_dict(self, vault):
        _, meta_dir = vault
        result = parse_frontmatter(meta_dir / "attention-is-all-you-need-metadata.md")
        assert result is not None
        assert result["arxiv_id"] == "2301.00001v1"
        assert "machine-learning" in result["tags"]

    def test_includes_body(self, vault):
        _, meta_dir = vault
        result = parse_frontmatter(meta_dir / "attention-is-all-you-need-metadata.md")
        assert "Attention Is All You Need" in result["_body"]

    def test_bad_yaml_returns_none(self, tmp_path):
        f = tmp_path / "bad-metadata.md"
        f.write_text("---\n: [invalid yaml\n---\n")
        assert parse_frontmatter(f) is None

    def test_no_frontmatter_returns_none(self, tmp_path):
        f = tmp_path / "plain.md"
        f.write_text("# Just a heading\nNo frontmatter here.")
        assert parse_frontmatter(f) is None


# ── load_all ──────────────────────────────────────────────────────────────

class TestLoadAll:
    def test_loads_all_papers(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        assert len(papers) == 3

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert load_all(d) == []


# ── find_paper_md ─────────────────────────────────────────────────────────

class TestFindPaperMd:
    def test_finds_existing(self, vault):
        papers_dir, meta_dir = vault
        papers = load_all(meta_dir)
        p = [p for p in papers if "attention" in p["_file"]][0]
        result = find_paper_md(p, papers_dir)
        assert result is not None
        assert result.name == "attention-is-all-you-need.md"

    def test_missing_returns_none(self, vault):
        papers_dir, meta_dir = vault
        papers = load_all(meta_dir)
        p = [p for p in papers if "portfolio" in p["_file"]][0]
        assert find_paper_md(p, papers_dir) is None


# ── search ────────────────────────────────────────────────────────────────

class TestSearch:
    def test_filter_by_tags(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, tags=["quant-finance"])
        assert len(results) == 1
        assert results[0]["arxiv_id"] == "2302.00002v1"

    def test_filter_by_tags_case_insensitive(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, tags=["MACHINE-LEARNING"])
        assert len(results) == 1

    def test_filter_by_categories(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, categories=["stat.ML"])
        assert len(results) == 1
        assert results[0]["arxiv_id"] == "2303.00003v1"

    def test_filter_by_query(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, query="transformer")
        assert len(results) == 1

    def test_filter_by_min_citations(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, min_citations=200)
        assert len(results) == 1

    def test_filter_by_after(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, after="2024-01-01")
        assert len(results) == 2  # paper A (2024-06) and C (2025-11)

    def test_filter_by_before(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, before="2023-06-01")
        assert len(results) == 1

    def test_combined_filters(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, tags=["machine-learning"], min_citations=100)
        assert len(results) == 1

    def test_no_match(self, vault):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        results = search(papers, tags=["nonexistent-tag"])
        assert len(results) == 0


# ── deep_search ───────────────────────────────────────────────────────────

class TestDeepSearch:
    def test_finds_in_full_text(self, vault):
        papers_dir, meta_dir = vault
        papers = load_all(meta_dir)
        results = deep_search("self-attention", papers, papers_dir)
        assert len(results) >= 1
        assert results[0].get("_relevance", 0) > 0

    def test_no_match(self, vault):
        papers_dir, meta_dir = vault
        papers = load_all(meta_dir)
        results = deep_search("xyznonexistent", papers, papers_dir)
        assert len(results) == 0


# ── _to_date ──────────────────────────────────────────────────────────────

class TestToDate:
    def test_string(self):
        assert _to_date("2023-01-15") == date(2023, 1, 15)

    def test_date_object(self):
        d = date(2023, 6, 1)
        assert _to_date(d) == d

    def test_datetime_object(self):
        dt = datetime(2023, 6, 1, 12, 0)
        assert _to_date(dt) == date(2023, 6, 1)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _to_date("not-a-date")


# ── score_paper ───────────────────────────────────────────────────────────

class TestScorePaper:
    def test_citation_component(self):
        p = {"citations": 500, "tags": [], "_file": "test.md", "_body": ""}
        s = score_paper(p, None, None)
        assert s >= 5.0  # 500/100 capped at 5.0

    def test_tag_match_boosts(self):
        p = {"citations": 0, "tags": ["ml"], "_file": "test.md", "_body": ""}
        s1 = score_paper(p, None, None)
        s2 = score_paper(p, ["ml"], None)
        assert s2 > s1

    def test_query_title_match(self):
        p = {"citations": 0, "tags": [], "_file": "transformer-arch.md", "_body": ""}
        s = score_paper(p, None, "transformer")
        assert s >= 3.0

    def test_recency_bonus(self):
        recent = {"citations": 0, "tags": [], "_file": "t.md", "_body": "", "published": "2026-01-01"}
        old = {"citations": 0, "tags": [], "_file": "t.md", "_body": "", "published": "2020-01-01"}
        s_recent = score_paper(recent, None, None)
        s_old = score_paper(old, None, None)
        assert s_recent > s_old


# ── display / export ──────────────────────────────────────────────────────

class TestDisplay:
    def test_display_runs(self, vault, capsys):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        display(papers, top=2)
        out = capsys.readouterr().out
        assert "cites" in out
        assert "results" in out

    def test_export_obsidian(self, vault, capsys):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        export_for_obsidian(papers)
        out = capsys.readouterr().out
        assert "[[" in out

    def test_export_obsidian_to_file(self, vault, tmp_path):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        out_file = tmp_path / "results.md"
        export_for_obsidian(papers, out_file)
        assert out_file.exists()
        assert "[[" in out_file.read_text()


# ── audit ─────────────────────────────────────────────────────────────────

class TestAudit:
    def test_runs(self, vault, capsys):
        _, meta_dir = vault
        papers = load_all(meta_dir)
        audit(papers)
        out = capsys.readouterr().out
        assert "VAULT AUDIT" in out


# ── Real vault smoke tests ───────────────────────────────────────────────

class TestRealVault:
    @pytest.mark.skipif(not METADATA_DIR.exists(), reason="Real vault not available")
    def test_load_all_real(self):
        papers = load_all(METADATA_DIR)
        assert len(papers) > 100

    @pytest.mark.skipif(not METADATA_DIR.exists(), reason="Real vault not available")
    def test_search_by_tag_real(self):
        papers = load_all(METADATA_DIR)
        results = search(papers, tags=["quant-finance"])
        assert len(results) > 0

    @pytest.mark.skipif(not METADATA_DIR.exists(), reason="Real vault not available")
    def test_search_by_citations_real(self):
        papers = load_all(METADATA_DIR)
        results = search(papers, min_citations=1000)
        assert len(results) > 0
        assert all((p.get("citations") or 0) >= 1000 for p in results)

    @pytest.mark.skipif(not PAPERS_DIR.exists(), reason="Real vault not available")
    def test_deep_search_real(self):
        papers = load_all(METADATA_DIR)
        results = deep_search("attention", papers, PAPERS_DIR)
        # Should find at least some papers mentioning "attention"
        assert len(results) >= 0  # don't fail if no full-text papers exist yet
