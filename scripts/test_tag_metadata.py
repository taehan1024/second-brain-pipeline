"""Tests for tag_metadata.py — runs against synthetic fixtures + real vault."""

import tempfile, shutil, textwrap
from pathlib import Path
import pytest

from tag_metadata import (
    parse_frontmatter, parse_frontmatter_text, get_body_from_text,
    build_tags_line, normalize_topic, suggest_tags_from_body,
    suggest_tags_from_content, tag_file, run_audit,
    CANONICAL_TAGS, TOPIC_TAGS, CONTENT_TAG_RULES, STRIP_TAGS,
    DEFAULT_METADATA_DIR,
)

# ── Fixtures ──────────────────────────────────────────────────────────────

SAMPLE_METADATA = textwrap.dedent("""\
    ---
    tags: [neural_network, papers]
    arxiv_id: 2301.00001v1
    categories: [cs.LG]
    published: 2023-01-15
    date_added: 2026-03-21
    citations: 500
    authors: "Alice, Bob"
    pdf: "sample-paper.pdf"
    source: "arXiv"
    priority: normal
    ---

    # Sample Paper

    **Authors:** Alice, Bob

    ## Abstract

    We propose a deep neural network for classification using gradient descent
    and attention mechanism with transformer architecture.
""")

SAMPLE_NO_TAGS = textwrap.dedent("""\
    ---
    arxiv_id: 2301.00002v1
    categories: [stat.ML]
    published: 2023-02-01
    citations: 100
    authors: "Eve"
    pdf: "no-tags.pdf"
    source: "arXiv"
    priority: normal
    ---

    # No Tags Paper

    ## Abstract

    A paper about lasso regularization and sparsity in high dimensions.
""")

SAMPLE_UNKNOWN_TOPIC = textwrap.dedent("""\
    ---
    tags: [some-random-topic]
    arxiv_id: 2301.00003v1
    categories: [cs.AI]
    published: 2023-03-01
    citations: 50
    authors: "Mallory"
    pdf: "unknown.pdf"
    source: "arXiv"
    priority: normal
    ---

    # Unknown Topic Paper

    ## Abstract

    This paper discusses portfolio optimization and risk measures.
""")


@pytest.fixture
def tmp_metadata(tmp_path):
    """Create a temp metadata dir with sample files."""
    d = tmp_path / "metadata"
    d.mkdir()
    (d / "sample-paper-metadata.md").write_text(SAMPLE_METADATA)
    (d / "no-tags-paper-metadata.md").write_text(SAMPLE_NO_TAGS)
    (d / "unknown-topic-metadata.md").write_text(SAMPLE_UNKNOWN_TOPIC)
    return d


# ── parse_frontmatter ─────────────────────────────────────────────────────

class TestParseFrontmatter:
    def test_parses_tags(self, tmp_metadata):
        tags, idx, text = parse_frontmatter(tmp_metadata / "sample-paper-metadata.md")
        assert "neural_network" in tags
        assert "papers" in tags
        assert idx is not None

    def test_no_tags_line(self, tmp_metadata):
        tags, idx, text = parse_frontmatter(tmp_metadata / "no-tags-paper-metadata.md")
        assert tags == []
        assert idx is None

    def test_text_variant_matches_file(self, tmp_metadata):
        path = tmp_metadata / "sample-paper-metadata.md"
        text = path.read_text()
        tags1, idx1, _ = parse_frontmatter(path)
        tags2, idx2, _ = parse_frontmatter_text(text)
        assert tags1 == tags2
        assert idx1 == idx2


class TestGetBody:
    def test_strips_frontmatter(self):
        body = get_body_from_text(SAMPLE_METADATA)
        assert "---" not in body.split("\n")[0]
        assert "Sample Paper" in body

    def test_no_frontmatter(self):
        plain = "# Just a heading\n\nSome text."
        assert get_body_from_text(plain) == plain


class TestBuildTagsLine:
    def test_format(self):
        assert build_tags_line(["a", "b"]) == "tags: [a, b]\n"

    def test_single(self):
        assert build_tags_line(["ml"]) == "tags: [ml]\n"


class TestNormalizeTopic:
    def test_dash_to_underscore(self):
        assert normalize_topic("neural-network") == "neural_network"

    def test_already_underscore(self):
        assert normalize_topic("neural_network") == "neural_network"


# ── suggest_tags_from_body ────────────────────────────────────────────────

class TestSuggestTags:
    def test_detects_deep_learning(self):
        body = "We use a neural network with attention mechanism."
        tags = suggest_tags_from_body(body)
        assert "deep-learning" in tags

    def test_detects_optimization(self):
        body = "We apply stochastic gradient descent with convergence rate analysis."
        tags = suggest_tags_from_body(body)
        assert "optimization" in tags

    def test_detects_quant_finance(self):
        body = "Portfolio optimization under volatility forecast constraints."
        tags = suggest_tags_from_body(body)
        assert "quant-finance" in tags

    def test_empty_body(self):
        assert suggest_tags_from_body("") == []

    def test_case_insensitive(self):
        body = "NEURAL NETWORK architecture with TRANSFORMER."
        tags = suggest_tags_from_body(body)
        assert "deep-learning" in tags

    def test_multiple_categories(self):
        body = "Bayesian neural network with variational inference for time series forecasting."
        tags = suggest_tags_from_body(body)
        assert "deep-learning" in tags
        assert "probabilistic-models" in tags
        assert "time-series" in tags


# ── tag_file ──────────────────────────────────────────────────────────────

class TestTagFile:
    def test_tags_known_topic(self, tmp_metadata):
        path = tmp_metadata / "sample-paper-metadata.md"
        changed, reason = tag_file(path)
        assert changed is True
        assert reason == "updated"
        # Re-read and verify tags
        tags, _, _ = parse_frontmatter(path)
        assert "neural-network" in tags
        assert "machine-learning" in tags
        assert "deep-learning" in tags
        assert "papers" not in tags  # stripped

    def test_idempotent(self, tmp_metadata):
        path = tmp_metadata / "sample-paper-metadata.md"
        tag_file(path)
        changed, reason = tag_file(path)
        assert changed is False
        assert reason == "unchanged"

    def test_unknown_topic_without_content(self, tmp_metadata):
        path = tmp_metadata / "unknown-topic-metadata.md"
        changed, reason = tag_file(path, use_content=False)
        assert changed is False
        assert reason == "unknown-topic"

    def test_unknown_topic_with_content(self, tmp_metadata):
        path = tmp_metadata / "unknown-topic-metadata.md"
        changed, reason = tag_file(path, use_content=True)
        assert changed is True
        tags, _, _ = parse_frontmatter(path)
        assert "quant-finance" in tags

    def test_no_frontmatter(self, tmp_metadata):
        path = tmp_metadata / "no-tags-paper-metadata.md"
        changed, reason = tag_file(path)
        assert changed is False
        assert reason == "no-frontmatter"

    def test_dry_run_does_not_write(self, tmp_metadata):
        path = tmp_metadata / "sample-paper-metadata.md"
        original = path.read_text()
        changed, reason = tag_file(path, dry_run=True)
        assert changed is True
        assert reason == "updated"
        assert path.read_text() == original  # file unchanged


# ── audit ─────────────────────────────────────────────────────────────────

class TestAudit:
    def test_runs_without_error(self, tmp_metadata, capsys):
        run_audit(tmp_metadata)
        out = capsys.readouterr().out
        assert "TAG AUDIT" in out
        assert "SUMMARY" in out

    def test_empty_dir(self, tmp_path, capsys):
        empty = tmp_path / "empty"
        empty.mkdir()
        run_audit(empty)
        out = capsys.readouterr().out
        assert "No metadata files found" in out


# ── Config consistency ────────────────────────────────────────────────────

class TestConfigConsistency:
    def test_topic_tags_values_are_canonical(self):
        """Every tag in TOPIC_TAGS values must be in CANONICAL_TAGS."""
        for topic, tags in TOPIC_TAGS.items():
            for t in tags:
                assert t in CANONICAL_TAGS, f"TOPIC_TAGS['{topic}'] has non-canonical tag '{t}'"

    def test_content_rules_produce_canonical_tags(self):
        """Every tag produced by CONTENT_TAG_RULES must be canonical."""
        for _, tag in CONTENT_TAG_RULES:
            assert tag in CANONICAL_TAGS, f"CONTENT_TAG_RULES produces non-canonical tag '{tag}'"

    def test_all_canonical_tags_have_content_rule(self):
        """Every canonical tag should be discoverable via content rules."""
        rule_tags = {tag for _, tag in CONTENT_TAG_RULES}
        for ct in CANONICAL_TAGS:
            assert ct in rule_tags, f"Canonical tag '{ct}' has no CONTENT_TAG_RULE"


# ── Real vault smoke test ────────────────────────────────────────────────

class TestRealVault:
    @pytest.mark.skipif(
        not DEFAULT_METADATA_DIR.exists(),
        reason="Real vault not available",
    )
    def test_parse_all_metadata(self):
        """Every metadata file in the real vault should parse without error."""
        files = list(DEFAULT_METADATA_DIR.glob("*-metadata.md"))
        assert len(files) > 0
        failures = []
        for f in files:
            try:
                tags, idx, text = parse_frontmatter(f)
            except Exception as e:
                failures.append((f.name, str(e)))
        assert failures == [], f"Parse failures: {failures}"

    @pytest.mark.skipif(
        not DEFAULT_METADATA_DIR.exists(),
        reason="Real vault not available",
    )
    def test_tag_file_dry_run_all(self):
        """Dry-run tagging on all real files should not raise."""
        files = list(DEFAULT_METADATA_DIR.glob("*-metadata.md"))
        for f in files:
            tag_file(f, use_content=True, dry_run=True)
