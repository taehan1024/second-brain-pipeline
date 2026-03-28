"""
tag_metadata.py
Tags metadata files with canonical brain tags.
Maps topic slugs → canonical tags, with audit and content-based suggestions.

Usage:
    python tag_metadata.py                    # apply topic→tag mapping
    python tag_metadata.py --audit            # report tag health
    python tag_metadata.py --suggest          # suggest tags from abstract content
    python tag_metadata.py --suggest --apply  # apply suggested tags
    python tag_metadata.py --synonyms         # find synonym/split tag issues
"""

import argparse
import re
from pathlib import Path
from collections import Counter

# ── CONFIG ──────────────────────────────────────────────────────────────────

DEFAULT_METADATA_DIR = Path(__file__).parent.parent / "10-Knowledge" / "metadata"

# ── CANONICAL TAG VOCABULARY ───────────────────────────────────────────────

CANONICAL_TAGS = {
    "machine-learning", "deep-learning", "high-dim-stats", "optimization",
    "quant-finance", "probabilistic-models", "time-series", "tensor-methods",
    "functional-data", "reinforcement-learning", "causal-inference",
}

# ── CONTENT → TAG RULES ───────────────────────────────────────────────────
# Keywords are pre-lowered at import time so we don't re-lower on every call.

CONTENT_TAG_RULES: list[tuple[list[str], str]] = [
    ([kw.lower() for kw in keywords], tag)
    for keywords, tag in [
        (["portfolio", "stock", "return prediction", "asset pricing", "factor model",
          "sharpe", "volatility forecast", "option pricing", "hedging",
          "market microstructure", "order book", "risk measure", "cryptocurrency",
          "regime switch"], "quant-finance"),
        (["time series", "time-series", "forecasting", "temporal",
          "autoregressive", "recurrent", "sequence model", "LSTM", "GRU"], "time-series"),
        (["neural network", "deep learn", "convolutional", "transformer",
          "attention mechanism", "encoder", "decoder", "pre-train",
          "fine-tun", "language model", "diffusion model", "GAN",
          "generative adversarial", "graph neural", "residual network"], "deep-learning"),
        (["reinforcement learn", "policy gradient", "Q-learn", "reward",
          "Markov decision", "bandit", "actor-critic", "PPO", "DQN"], "reinforcement-learning"),
        (["high dimension", "high-dimension", "sparsity", "sparse",
          "lasso", "regulariz", "penaliz", "covariance estimation",
          "random matrix", "concentration inequal", "minimax"], "high-dim-stats"),
        (["convex optim", "non-convex", "nonconvex", "gradient descent",
          "stochastic gradient", "proximal", "Frank-Wolfe", "mirror descent",
          "convergence rate", "optimization algorithm", "linear programming",
          "semidefinite", "ADMM"], "optimization"),
        (["tensor", "decomposition", "Tucker", "CP decomposition",
          "tensor factorization", "multilinear"], "tensor-methods"),
        (["functional data", "function space", "Hilbert space",
          "reproducing kernel", "RKHS", "functional regression"], "functional-data"),
        (["Bayesian", "posterior", "prior distribution", "MCMC",
          "variational inference", "probabilistic model", "Gaussian process",
          "expectation maximization", "mixture model", "latent variable"], "probabilistic-models"),
        (["causal", "treatment effect", "instrumental variable",
          "counterfactual", "propensity score", "do-calculus"], "causal-inference"),
        (["machine learn", "supervised learn", "unsupervised learn",
          "classification", "regression", "feature select", "cross-validation",
          "ensemble", "boosting", "random forest", "kernel method",
          "support vector"], "machine-learning"),
    ]
]

# ── TOPIC → CANONICAL TAGS MAPPING ─────────────────────────────────────────

TOPIC_TAGS: dict[str, list[str]] = {
    "survival_analysis":            ["machine-learning", "high-dim-stats", "probabilistic-models"],
    "mixed_effects_model":          ["machine-learning", "high-dim-stats", "probabilistic-models"],
    "time_series_forecasting":      ["machine-learning", "time-series"],
    "anomaly_detection":            ["machine-learning"],
    "gradient_boosting":            ["machine-learning"],
    "bayesian_deep_learning":       ["machine-learning", "deep-learning", "probabilistic-models"],
    "uncertainty_quantification":   ["machine-learning", "probabilistic-models"],
    "interpretable_machine_learning": ["machine-learning"],
    "sports_analytics":             ["machine-learning"],
    "neural_network":               ["machine-learning", "deep-learning"],
    "transformer_architecture":     ["machine-learning", "deep-learning"],
    "large_language_model":         ["machine-learning", "deep-learning"],
    "reinforcement_learning":       ["machine-learning", "reinforcement-learning"],
    "diffusion_model":              ["machine-learning", "deep-learning", "probabilistic-models"],
    "graph_neural_network":         ["machine-learning", "deep-learning"],
    "contrastive_learning":         ["machine-learning", "deep-learning"],
    "self_supervised_learning":     ["machine-learning", "deep-learning"],
    "mixture_of_experts":           ["machine-learning", "deep-learning"],
    "state_space_model":            ["machine-learning", "high-dim-stats"],
    "retrieval_augmented_generation": ["machine-learning", "deep-learning"],
    "chain_of_thought_reasoning":   ["machine-learning", "deep-learning"],
    "meta_learning":                ["machine-learning"],
    "federated_learning":           ["machine-learning"],
    "knowledge_distillation":       ["machine-learning", "deep-learning"],
    "high_dimensional_statistics":  ["high-dim-stats"],
    "sparse_estimation":            ["high-dim-stats", "optimization"],
    "functional_data_analysis":     ["high-dim-stats", "functional-data"],
    "tensor_decomposition":         ["high-dim-stats", "tensor-methods"],
    "random_matrix_theory":         ["high-dim-stats"],
    "principal_component_analysis": ["high-dim-stats"],
    "lasso_regularization":         ["high-dim-stats", "optimization"],
    "compressed_sensing":           ["high-dim-stats"],
    "matrix_completion":            ["high-dim-stats", "optimization"],
    "gaussian_process":             ["machine-learning", "high-dim-stats", "probabilistic-models"],
    "variational_inference":        ["machine-learning", "probabilistic-models"],
    "expectation_maximization":     ["machine-learning", "probabilistic-models"],
    "causal_inference":             ["high-dim-stats", "causal-inference"],
    "multiple_testing":             ["high-dim-stats"],
    "nonparametric_statistics":     ["high-dim-stats"],
    "kernel_methods":               ["machine-learning", "high-dim-stats"],
    "reproducing_kernel_hilbert_space": ["machine-learning", "high-dim-stats"],
    "convex_optimization":          ["optimization"],
    "stochastic_gradient_descent":  ["optimization", "machine-learning"],
    "proximal_gradient":            ["optimization"],
    "bayesian_optimization":        ["optimization", "machine-learning", "probabilistic-models"],
    "zeroth_order_optimization":    ["optimization"],
    "mirror_descent":               ["optimization"],
    "frank_wolfe_algorithm":        ["optimization"],
    "online_convex_optimization":   ["optimization"],
    "semidefinite_programming":     ["optimization"],
    "nonconvex_optimization":       ["optimization"],
    "second_order_optimization":    ["optimization"],
    "portfolio_optimization":       ["quant-finance", "optimization"],
    "stochastic_volatility":        ["quant-finance", "probabilistic-models"],
    "deep_hedging":                 ["quant-finance", "machine-learning"],
    "option_pricing_machine_learning": ["quant-finance", "machine-learning"],
    "factor_model_finance":         ["quant-finance"],
    "market_microstructure":        ["quant-finance"],
    "limit_order_book":             ["quant-finance"],
    "cryptocurrency_price_prediction": ["quant-finance", "machine-learning"],
    "regime_switching":             ["quant-finance", "probabilistic-models"],
    "risk_measures":                ["quant-finance"],
    "volatility_forecasting":       ["quant-finance", "time-series"],
}

STRIP_TAGS = {"papers"}

# ── HELPERS ─────────────────────────────────────────────────────────────────

def parse_frontmatter(path: Path) -> tuple[list[str], int | None, str]:
    """Parse YAML frontmatter, returning (tags, tags_line_index, full_text)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_frontmatter_text(text)


def parse_frontmatter_text(text: str) -> tuple[list[str], int | None, str]:
    """Parse frontmatter from already-loaded text (avoids redundant I/O)."""
    lines = text.splitlines(keepends=True)
    in_fm = False
    tags_idx = None
    tags = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                break
        if in_fm and stripped.startswith("tags:"):
            tags_idx = i
            m = re.search(r"\[(.+?)\]", stripped)
            if m:
                tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
    return tags, tags_idx, text


def get_body_from_text(text: str) -> str:
    """Extract body (post-frontmatter) from already-loaded text."""
    m = re.match(r"^---\s*\n.+?\n---\s*\n?", text, re.DOTALL)
    if m:
        return text[m.end():]
    return text


def get_body_text(path: Path) -> str:
    """Read file and return body text after frontmatter."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return get_body_from_text(text)


def build_tags_line(tags: list[str]) -> str:
    return f"tags: [{', '.join(tags)}]\n"


def normalize_topic(tag: str) -> str:
    return tag.replace("-", "_")


# ── CONTENT-BASED TAG SUGGESTIONS ──────────────────────────────────────────

def suggest_tags_from_body(body: str) -> list[str]:
    """Suggest canonical tags from body text (already lowered)."""
    body_lower = body.lower()
    suggested = set()
    for keywords, tag in CONTENT_TAG_RULES:
        for kw in keywords:
            if kw in body_lower:
                suggested.add(tag)
                break
    return sorted(suggested)


def suggest_tags_from_content(path: Path) -> list[str]:
    """Suggest tags by reading a file (convenience wrapper)."""
    return suggest_tags_from_body(get_body_text(path))


# ── CORE TAGGING ───────────────────────────────────────────────────────────

def tag_file(path: Path, use_content: bool = False, dry_run: bool = False) -> tuple[bool, str]:
    """Tag a single metadata file. Returns (changed, reason).

    When dry_run=True, computes what would change but does not write.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    tags, tags_idx, _ = parse_frontmatter_text(text)
    lines = text.splitlines(keepends=True)

    if tags_idx is None:
        return False, "no-frontmatter"

    tags = [t for t in tags if t not in STRIP_TAGS]

    topic_slug = None
    for t in tags:
        normalized = normalize_topic(t)
        if normalized in TOPIC_TAGS:
            topic_slug = normalized
            break

    if topic_slug is None and not use_content:
        return False, "unknown-topic"

    seen = set()
    merged = []

    if topic_slug:
        topic_tag = topic_slug.replace("_", "-")
        canonical = TOPIC_TAGS[topic_slug]
        for t in [topic_tag] + canonical:
            if t not in seen:
                seen.add(t)
                merged.append(t)

    if use_content:
        body = get_body_from_text(text)
        content_tags = suggest_tags_from_body(body)
        for t in content_tags:
            if t not in seen:
                seen.add(t)
                merged.append(t)

    if not merged:
        return False, "no-tags-found"

    new_line = build_tags_line(merged)
    if lines[tags_idx] == new_line:
        return False, "unchanged"

    if not dry_run:
        lines[tags_idx] = new_line
        path.write_text("".join(lines))

    return True, "updated"


# ── AUDIT ──────────────────────────────────────────────────────────────────

def run_audit(metadata_dir: Path):
    files = sorted(metadata_dir.glob("*-metadata.md"))
    if not files:
        print("No metadata files found.")
        return

    print(f"=== TAG AUDIT: {len(files)} files ===\n")

    all_tags = Counter()
    no_canonical = []
    single_tag = []
    missing_content_tags = []
    canonical_count = 0

    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        tags, _, _ = parse_frontmatter_text(text)
        tags_clean = [t for t in tags if t not in STRIP_TAGS]

        for t in tags_clean:
            all_tags[t] += 1

        has_canonical = any(t in CANONICAL_TAGS for t in tags_clean)
        if has_canonical:
            canonical_count += 1
        else:
            no_canonical.append((f.name, tags_clean))

        if len(tags_clean) <= 1:
            single_tag.append((f.name, tags_clean))

        body = get_body_from_text(text)
        suggested = suggest_tags_from_body(body)
        new_suggestions = [t for t in suggested if t not in tags_clean]
        if new_suggestions:
            missing_content_tags.append((f.name, tags_clean, new_suggestions))

    print("TAG DISTRIBUTION:")
    for tag, count in all_tags.most_common(30):
        marker = "\u2713" if tag in CANONICAL_TAGS else "\u25cb"
        print(f"  {marker} {tag}: {count}")
    print()

    print(f"PAPERS MISSING CANONICAL TAGS: {len(no_canonical)}")
    for name, tags in no_canonical[:10]:
        print(f"  {name}  \u2192  {tags}")
    if len(no_canonical) > 10:
        print(f"  ... and {len(no_canonical) - 10} more")
    print()

    print(f"PAPERS WITH \u22641 TAG: {len(single_tag)}")
    for name, tags in single_tag[:10]:
        print(f"  {name}  \u2192  {tags}")
    print()

    print(f"CONTENT-BASED SUGGESTIONS (papers missing tags their abstract implies): {len(missing_content_tags)}")
    for name, current, suggested in missing_content_tags[:15]:
        print(f"  {name}")
        print(f"    current:   {current}")
        print(f"    suggested: +{suggested}")
    if len(missing_content_tags) > 15:
        print(f"  ... and {len(missing_content_tags) - 15} more")
    print()

    print(f"SUMMARY:")
    print(f"  Total papers: {len(files)}")
    print(f"  With canonical tags: {canonical_count} ({canonical_count/len(files)*100:.0f}%)")
    print(f"  Missing canonical: {len(no_canonical)}")
    print(f"  Would gain tags from content analysis: {len(missing_content_tags)}")


# ── SYNONYM DETECTION ──────────────────────────────────────────────────────

KNOWN_SYNONYMS = {
    frozenset({"finance", "quant-finance"}): "quant-finance",
    frozenset({"dl", "deep-learning"}): "deep-learning",
    frozenset({"ml", "machine-learning"}): "machine-learning",
    frozenset({"stats", "statistics", "high-dim-stats"}): "high-dim-stats",
    frozenset({"optim", "optimization"}): "optimization",
    frozenset({"timeseries", "time-series"}): "time-series",
    frozenset({"rl", "reinforcement-learning"}): "reinforcement-learning",
}

def check_synonyms(metadata_dir: Path):
    files = sorted(metadata_dir.glob("*-metadata.md"))
    all_tags = Counter()
    for f in files:
        tags, _, _ = parse_frontmatter(f)
        for t in tags:
            all_tags[t] += 1

    print("=== SYNONYM CHECK ===\n")

    all_tag_set = set(all_tags.keys())
    issues = []
    for syn_group, canonical in KNOWN_SYNONYMS.items():
        found = syn_group & all_tag_set
        if len(found) > 1:
            issues.append((canonical, found, {t: all_tags[t] for t in found}))

    if issues:
        for canonical, found, counts in issues:
            print(f"  SPLIT: {found} \u2192 should all be '{canonical}'")
            for t, c in counts.items():
                print(f"    {t}: {c} papers")
            print()
    else:
        print("  No synonym splits found.\n")

    topic_tags = set()
    for t in all_tags:
        if normalize_topic(t) in TOPIC_TAGS:
            topic_tags.add(t)
    unmapped = all_tag_set - CANONICAL_TAGS - topic_tags - STRIP_TAGS
    if unmapped:
        print(f"UNMAPPED TAGS (not canonical, not topic slugs):")
        for t in sorted(unmapped):
            print(f"    {t}: {all_tags[t]}")


# ── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Tag metadata files with canonical brain tags")
    parser.add_argument("--dir", type=str, default=str(DEFAULT_METADATA_DIR))
    parser.add_argument("--audit", action="store_true", help="Report tag health without changing files")
    parser.add_argument("--suggest", action="store_true", help="Suggest tags from abstract content")
    parser.add_argument("--apply", action="store_true", help="With --suggest, write suggestions to files")
    parser.add_argument("--synonyms", action="store_true", help="Check for synonym/split tag issues")
    args = parser.parse_args()

    metadata_dir = Path(args.dir)

    if args.audit:
        run_audit(metadata_dir)
        return

    if args.synonyms:
        check_synonyms(metadata_dir)
        return

    files = sorted(metadata_dir.glob("*-metadata.md"))
    print(f"Found {len(files)} metadata files in {metadata_dir}\n")

    use_content = args.suggest
    dry_run = args.suggest and not args.apply
    updated = 0
    skipped = 0
    unknown = 0

    for f in files:
        modified, reason = tag_file(f, use_content=use_content, dry_run=dry_run)
        if modified:
            updated += 1
        elif reason == "unknown-topic":
            unknown += 1
        else:
            skipped += 1

    action = "Would update" if dry_run else "Updated"
    print(f"\u2705 {action} : {updated}")
    print(f"\u23ed  Skipped : {skipped}  (unchanged)")
    print(f"\u2753 Unknown : {unknown}  (no topic slug matched)")

    if dry_run:
        print("\nDry run \u2014 no files changed. Add --apply to write.")


if __name__ == "__main__":
    main()
