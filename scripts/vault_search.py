"""
Search your arxiv metadata vault.

Usage:
    python vault_search.py --tags finance optimization
    python vault_search.py --query "attention mechanism"
    python vault_search.py --query "cross-sectional return" --deep
    python vault_search.py --tags time-series --min-citations 100
    python vault_search.py --categories cs.LG --after 2023-01-01
    python vault_search.py --all --sort citations --top 20
    python vault_search.py --project stock-prediction
    python vault_search.py --gaps stock-prediction
    python vault_search.py --gaps stock-prediction --deep
    python vault_search.py --gaps-init "recommender system for personalized ranking"
    python vault_search.py --audit
    python vault_search.py --tags finance --prompt "extract features used"
"""

import argparse, re, json
from pathlib import Path
from datetime import datetime
from collections import Counter

import yaml

SCRIPT_DIR = Path(__file__).parent
METADATA_DIR = SCRIPT_DIR.parent / "10-Knowledge" / "metadata"
PAPERS_DIR = SCRIPT_DIR.parent / "10-Knowledge" / "arxiv_mds"
PROJECTS_DIR = SCRIPT_DIR.parent / "30-Projects" / "active"

CANONICAL_TAGS = {
    "machine-learning", "deep-learning", "high-dim-stats", "optimization",
    "quant-finance", "probabilistic-models", "time-series", "tensor-methods",
    "functional-data", "reinforcement-learning", "causal-inference",
}

# --- Knowledge Map ---
# For a given problem, what research areas should be covered?
# Each area has: description, required tags (OR), search keywords for deep matching,
# and arxiv_downloader query to fill the gap.

KNOWLEDGE_MAP = {
    "stock-prediction": {
        "description": "Cross-sectional equity return prediction",
        "areas": {
            "factor-models": {
                "description": "Fama-French, APT, factor construction, factor zoo",
                "tags": ["quant-finance"],
                "keywords": ["factor model", "fama french", "asset pricing", "cross-sectional", "factor zoo"],
                "arxiv_query": "factor model asset pricing cross-sectional",
                "min_papers": 5,
            },
            "return-prediction-ml": {
                "description": "ML models for return prediction (Gu-Kelly-Xiu, etc.)",
                "tags": ["quant-finance", "machine-learning"],
                "keywords": ["return prediction", "stock prediction", "equity prediction", "expected return"],
                "arxiv_query": "machine learning stock return prediction",
                "min_papers": 5,
            },
            "time-series-models": {
                "description": "Temporal architectures (LSTM, transformers, SSMs for finance)",
                "tags": ["time-series"],
                "keywords": ["time series", "temporal", "sequence model", "autoregressive", "LSTM", "state space"],
                "arxiv_query": "time series forecasting deep learning",
                "min_papers": 5,
            },
            "portfolio-construction": {
                "description": "Mean-variance, risk parity, transaction costs, turnover",
                "tags": ["quant-finance", "optimization"],
                "keywords": ["portfolio", "mean variance", "risk parity", "transaction cost", "turnover"],
                "arxiv_query": "portfolio optimization transaction costs",
                "min_papers": 3,
            },
            "regularization": {
                "description": "Lasso, ridge, elastic net, sparse estimation in high-dim",
                "tags": ["high-dim-stats", "optimization"],
                "keywords": ["lasso", "ridge", "elastic net", "sparse", "regulariz", "penaliz"],
                "arxiv_query": "sparse estimation high dimensional regularization",
                "min_papers": 5,
            },
            "covariance-estimation": {
                "description": "High-dim covariance, shrinkage, factor covariance",
                "tags": ["high-dim-stats"],
                "keywords": ["covariance estimation", "shrinkage", "precision matrix", "factor covariance"],
                "arxiv_query": "high dimensional covariance estimation shrinkage",
                "min_papers": 3,
            },
            "volatility": {
                "description": "Realized vol, GARCH, stochastic vol, vol forecasting",
                "tags": ["quant-finance", "time-series"],
                "keywords": ["volatility", "GARCH", "realized volatil", "stochastic volatil"],
                "arxiv_query": "volatility forecasting stochastic",
                "min_papers": 3,
            },
            "feature-engineering": {
                "description": "Technical indicators, feature selection, feature importance",
                "tags": ["machine-learning"],
                "keywords": ["feature select", "feature importance", "technical indicator", "feature engineer"],
                "arxiv_query": "feature selection importance machine learning",
                "min_papers": 3,
            },
            "evaluation-backtest": {
                "description": "Walk-forward validation, backtest pitfalls, multiple testing",
                "tags": ["high-dim-stats"],
                "keywords": ["backtest", "walk forward", "look-ahead bias", "multiple testing", "false discovery"],
                "arxiv_query": "backtesting overfitting multiple testing finance",
                "min_papers": 2,
            },
            "tree-models": {
                "description": "Gradient boosting, random forests, XGBoost, LightGBM for tabular",
                "tags": ["machine-learning"],
                "keywords": ["gradient boosting", "random forest", "XGBoost", "LightGBM", "tabular", "tree model"],
                "arxiv_query": "gradient boosting tabular data",
                "min_papers": 3,
            },
        },
    },
    "baseball-analytics": {
        "description": "KBO/MLB sabermetrics and prediction",
        "areas": {
            "sabermetrics": {
                "description": "WAR, wOBA, pitch modeling, win probability",
                "tags": ["machine-learning"],
                "keywords": ["baseball", "sabermetric", "pitch", "batter", "WAR", "win probability"],
                "arxiv_query": "baseball analytics machine learning",
                "min_papers": 3,
            },
            "sports-prediction": {
                "description": "Game outcome prediction, player performance modeling",
                "tags": ["machine-learning", "probabilistic-models"],
                "keywords": ["sports predict", "game outcome", "player performance", "ranking model"],
                "arxiv_query": "sports prediction machine learning",
                "min_papers": 3,
            },
            "tracking-data": {
                "description": "Statcast, trajectory modeling, computer vision for sports",
                "tags": ["machine-learning", "deep-learning"],
                "keywords": ["tracking data", "trajectory", "computer vision sport", "statcast", "pose estimation"],
                "arxiv_query": "sports tracking data computer vision",
                "min_papers": 2,
            },
            "bayesian-ranking": {
                "description": "Elo, Bradley-Terry, Bayesian skill models",
                "tags": ["probabilistic-models"],
                "keywords": ["Elo", "Bradley-Terry", "ranking", "skill model", "paired comparison"],
                "arxiv_query": "Bayesian ranking Bradley-Terry sports",
                "min_papers": 2,
            },
            "time-series-sports": {
                "description": "Streaks, slumps, regime changes in performance",
                "tags": ["time-series", "probabilistic-models"],
                "keywords": ["streak", "hot hand", "regime", "changepoint", "performance time series"],
                "arxiv_query": "changepoint detection time series sports",
                "min_papers": 2,
            },
        },
    },
    
    "recommender-system-for-personalized-cont": {
        "description": "recommender system for personalized content ranking",
        "areas": {
            "machine-learning": {
                "description": "language models, matrix completion, siren sign",
                "tags": ["machine-learning"],
                "keywords": ["language models", "matrix completion", "recommender systems", "large language", "global context", "graph neural"],
                "arxiv_query": "language models matrix completion recommender systems large language",
                "min_papers": 5,
            },
            "high-dim-stats": {
                "description": "matrix completion, inexact soft, large scale",
                "tags": ["high-dim-stats"],
                "keywords": ["matrix completion", "recommender systems", "underlying matrix", "global context", "tensor completion", "low-rank matrix"],
                "arxiv_query": "matrix completion recommender systems underlying matrix global context",
                "min_papers": 5,
            },
            "deep-learning": {
                "description": "language models, siren sign, aware recommendation",
                "tags": ["deep-learning"],
                "keywords": ["language models", "large language", "global context", "graph neural", "neural networks", "recommender systems"],
                "arxiv_query": "language models large language global context graph neural",
                "min_papers": 5,
            },
            "optimization": {
                "description": "matrix completion, inexact soft, large scale",
                "tags": ["optimization"],
                "keywords": ["matrix completion", "recommender systems", "underlying matrix", "tensor completion", "horror films", "observations"],
                "arxiv_query": "matrix completion recommender systems underlying matrix tensor completion",
                "min_papers": 3,
            },
            "tensor-methods": {
                "description": "inexact soft, large scale, tensor completion",
                "tags": ["tensor-methods"],
                "keywords": ["tensor completion", "matrix", "soft-impute", "structure"],
                "arxiv_query": "tensor completion matrix soft-impute structure",
                "min_papers": 3,
            },
            "causal-inference": {
                "description": "causal matrix",
                "tags": ["causal-inference"],
                "keywords": ["matrix completion", "underlying matrix", "horror films", "random"],
                "arxiv_query": "matrix completion underlying matrix horror films random",
                "min_papers": 3,
            },
            "reinforcement-learning": {
                "description": "distilling knowledge, fast retrieval, chat bots",
                "tags": ["reinforcement-learning"],
                "keywords": ["conversation history", "response"],
                "arxiv_query": "conversation history response",
                "min_papers": 3,
            },
            "probabilistic-models": {
                "description": "fixed effects, high dimensional, linear mixed",
                "tags": ["probabilistic-models"],
                "keywords": ["linear mixed", "mixed models", "unobserved heterogeneity", "test"],
                "arxiv_query": "linear mixed mixed models unobserved heterogeneity test",
                "min_papers": 3,
            },
        },
    },
    
    
    
    
    "crypto-investing": {
        "description": "Cryptocurrency price prediction and portfolio management",
        "areas": {
            "crypto-prediction": {
                "description": "Bitcoin/altcoin price forecasting",
                "tags": ["quant-finance", "machine-learning"],
                "keywords": ["bitcoin", "cryptocurrency", "crypto", "blockchain", "digital asset"],
                "arxiv_query": "cryptocurrency price prediction machine learning",
                "min_papers": 3,
            },
            "on-chain-analytics": {
                "description": "Blockchain data features, network analysis",
                "tags": ["quant-finance"],
                "keywords": ["on-chain", "blockchain analyt", "network analysis", "transaction graph"],
                "arxiv_query": "blockchain on-chain analytics prediction",
                "min_papers": 2,
            },
            "defi": {
                "description": "DeFi protocols, AMMs, yield optimization",
                "tags": ["quant-finance", "optimization"],
                "keywords": ["DeFi", "automated market maker", "liquidity pool", "yield", "AMM"],
                "arxiv_query": "DeFi automated market maker optimization",
                "min_papers": 2,
            },
            "crypto-volatility": {
                "description": "Crypto-specific volatility patterns, regime switching",
                "tags": ["quant-finance", "time-series"],
                "keywords": ["crypto volatil", "bitcoin volatil", "regime switch", "jump diffusion"],
                "arxiv_query": "cryptocurrency volatility regime switching",
                "min_papers": 2,
            },
        },
    },
}


def _count_area_coverage(
    papers: list[dict],
    area: dict,
    papers_dir: Path,
    deep: bool = False,
) -> tuple[int, list[dict]]:
    tag_matches = []
    for p in papers:
        ptags = [t.lower() for t in p.get("tags", [])]
        if any(t.lower() in ptags for t in area["tags"]):
            tag_matches.append(p)

    if not deep:
        keyword_hits = []
        for p in tag_matches:
            body = p.get("_body", "").lower()
            title = p.get("_file", "").lower()
            for kw in area["keywords"]:
                if kw.lower() in body or kw.lower() in title:
                    keyword_hits.append(p)
                    break
        return len(keyword_hits), keyword_hits

    keyword_hits = []
    for p in tag_matches:
        md_path = find_paper_md(p, papers_dir)
        if md_path is None:
            continue
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace").lower()
            for kw in area["keywords"]:
                if kw.lower() in content:
                    keyword_hits.append(p)
                    break
        except Exception:
            continue
    return len(keyword_hits), keyword_hits


def run_gaps(
    problem: str,
    papers: list[dict],
    papers_dir: Path,
    deep: bool = False,
):
    if problem not in KNOWLEDGE_MAP:
        print(f"Unknown problem: '{problem}'")
        print(f"Available: {', '.join(KNOWLEDGE_MAP.keys())}")
        print(f"\nOr define a custom problem in KNOWLEDGE_MAP in vault_search.py")
        return

    spec = KNOWLEDGE_MAP[problem]
    print(f"=== KNOWLEDGE GAP ANALYSIS: {problem} ===")
    print(f"{spec['description']}")
    print(f"Scanning {len(papers)} papers {'(deep mode)' if deep else '(metadata only)'}\n")

    strong = []
    weak = []
    missing = []
    download_commands = []

    for area_name, area in spec["areas"].items():
        count, hits = _count_area_coverage(papers, area, papers_dir, deep)
        min_needed = area["min_papers"]
        gap = max(0, min_needed - count)

        if count >= min_needed:
            status = "✅"
            strong.append((area_name, count, area))
        elif count > 0:
            status = "🟡"
            weak.append((area_name, count, min_needed, gap, area))
        else:
            status = "❌"
            missing.append((area_name, min_needed, area))

        top_paper = ""
        if hits:
            best = sorted(hits, key=lambda p: p.get("citations", 0) or 0, reverse=True)[0]
            top_paper = f"  best: {best['_file'][:50]}... ({best.get('citations', '?')} cites)"

        print(f"  {status} {area_name}: {count}/{min_needed} papers — {area['description']}")
        if top_paper:
            print(f"    {top_paper}")

    print()
    print("=" * 60)
    print(f"STRONG ({len(strong)}): {', '.join(a[0] for a in strong)}")
    print(f"WEAK   ({len(weak)}): {', '.join(a[0] for a in weak)}")
    print(f"MISSING({len(missing)}): {', '.join(a[0] for a in missing)}")
    print("=" * 60)

    if weak or missing:
        print(f"\n📥 SUGGESTED DOWNLOADS:")
        print(f"Run these to fill gaps:\n")
        for name, count, needed, gap, area in weak:
            print(f"# {name}: have {count}, need {gap} more")
            print(f"python3 arxiv_downloader.py --topic \"{area['arxiv_query']}\" --max {gap + 3} --min-citations 20")
            print()
        for name, needed, area in missing:
            print(f"# {name}: have 0, need {needed}")
            print(f"python3 arxiv_downloader.py --topic \"{area['arxiv_query']}\" --max {needed + 5} --min-citations 20")
            print()

        print("After downloading, run:")
        print("  python3 pdf_to_md.py")
        print("  python3 tag_metadata.py --suggest --apply")
        print(f"  python3 vault_search.py --gaps {problem}  # re-check")

    else:
        print(f"\n✅ Full coverage for {problem}. Ready to synthesize.")
        print(f"Next: write synthesis notes, then build.")


# --- Parsing ---

def parse_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.+?)\n---", text, re.DOTALL)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1))
        meta["_file"] = path.name
        meta["_body"] = text[m.end():]
        meta["_path"] = str(path)
        return meta
    except yaml.YAMLError:
        return None


def load_all(metadata_dir: Path = METADATA_DIR) -> list[dict]:
    papers = []
    for f in sorted(metadata_dir.glob("*-metadata.md")):
        meta = parse_frontmatter(f)
        if meta:
            papers.append(meta)
    return papers


# --- Full-text search over paper MDs ---

def find_paper_md(paper: dict, papers_dir: Path = PAPERS_DIR) -> Path | None:
    slug = paper["_file"].replace("-metadata.md", "")
    for topic_dir in papers_dir.iterdir():
        if not topic_dir.is_dir() or topic_dir.name.startswith((".", "_")):
            continue
        if topic_dir.name == "metadata":
            continue
        candidate = topic_dir / f"{slug}.md"
        if candidate.exists():
            return candidate
    return None


def deep_search(query: str, papers: list[dict], papers_dir: Path = PAPERS_DIR) -> list[dict]:
    q = query.lower()
    variants = {q, q.replace("-", " "), q.replace(" ", "-")}
    results = []
    for p in papers:
        md_path = find_paper_md(p, papers_dir)
        if md_path is None:
            continue
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace").lower()
            total_hits = sum(content.count(v) for v in variants)
            if total_hits > 0:
                p["_relevance"] = total_hits
                p["_md_path"] = str(md_path)
                results.append(p)
        except Exception:
            continue
    return sorted(results, key=lambda p: p.get("_relevance", 0), reverse=True)


# --- Project-aware search ---

def load_project_context(project_name: str, projects_dir: Path = PROJECTS_DIR) -> dict:
    index_path = projects_dir / project_name / "index.md"
    if not index_path.exists():
        print(f"Project index not found: {index_path}")
        return {}

    text = index_path.read_text(encoding="utf-8", errors="replace")

    tags = set()
    tag_patterns = [
        r"\[\[.*?\]\]",
        r"#([\w-]+)",
    ]
    for section in ["Key Research", "Synthesis Notes", "Design Decisions"]:
        idx = text.find(section)
        if idx == -1:
            continue
        chunk = text[idx:idx+2000]
        for pat in tag_patterns:
            for m in re.finditer(pat, chunk):
                tags.add(m.group(0).strip("[]#"))

    keywords = set()
    for section in ["Thesis", "Key findings"]:
        idx = text.find(section)
        if idx == -1:
            continue
        chunk = text[idx:idx+500].lower()
        for word in re.findall(r"[a-z]{4,}", chunk):
            if word not in {"this", "that", "with", "from", "into", "than", "more", "most", "have", "been", "were", "will", "also", "each", "when", "what"}:
                keywords.add(word)

    return {"tags": list(tags)[:10], "keywords": list(keywords)[:15]}


# --- Relevance scoring ---

def score_paper(paper: dict, tags: list[str] | None, query: str | None) -> float:
    score = 0.0
    cites = paper.get("citations") or 0
    score += min(cites / 100, 5.0)

    if tags:
        paper_tags = [t.lower() for t in paper.get("tags", [])]
        matches = sum(1 for t in tags if t.lower() in paper_tags)
        score += matches * 2.0

    if query:
        q = query.lower()
        variants = {q, q.replace("-", " "), q.replace(" ", "-")}
        body = paper.get("_body", "").lower()
        title = paper.get("_file", "").lower()
        if any(v in title for v in variants):
            score += 3.0
        hits = sum(body.count(v) for v in variants)
        if hits > 0:
            score += 1.0 + hits * 0.2

    pub = paper.get("published")
    if pub:
        try:
            d = _to_date(pub)
            days_old = (datetime.now().date() - d).days
            score += max(0, 2.0 - days_old / 365)
        except Exception:
            pass

    score += paper.get("_relevance", 0) * 0.5

    return round(score, 2)


# --- Search ---

def search(
    papers: list[dict],
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    query: str | None = None,
    min_citations: int = 0,
    after: str | None = None,
    before: str | None = None,
) -> list[dict]:
    results = papers

    if tags:
        tags_lower = [t.lower() for t in tags]
        results = [
            p for p in results
            if any(t.lower() in [x.lower() for x in p.get("tags", [])] for t in tags_lower)
        ]

    if categories:
        cats_lower = [c.lower() for c in categories]
        results = [
            p for p in results
            if any(c.lower() in [x.lower() for x in p.get("categories", [])] for c in cats_lower)
        ]

    if query:
        q = query.lower()
        variants = {q, q.replace("-", " "), q.replace(" ", "-")}
        results = [
            p for p in results
            if any(
                v in p.get("_file", "").lower()
                or v in str(p.get("tags", "")).lower()
                or v in p.get("_body", "").lower()
                or v in str(p.get("authors", "")).lower()
                for v in variants
            )
        ]

    if min_citations:
        results = [p for p in results if (p.get("citations") or 0) >= min_citations]

    if after:
        dt = datetime.strptime(after, "%Y-%m-%d").date()
        results = [
            p for p in results
            if p.get("published") and _to_date(p["published"]) >= dt
        ]

    if before:
        dt = datetime.strptime(before, "%Y-%m-%d").date()
        results = [
            p for p in results
            if p.get("published") and _to_date(p["published"]) <= dt
        ]

    return results


def _to_date(val):
    if isinstance(val, datetime):
        return val.date()
    if hasattr(val, "date"):
        return val if not callable(getattr(val, "date", None)) else val.date()
    return datetime.strptime(str(val), "%Y-%m-%d").date()


# --- Audit ---

def audit(papers: list[dict], fix: bool = False) -> None:
    print(f"=== VAULT AUDIT: {len(papers)} papers ===\n")

    all_tags = Counter()
    no_tags = []
    topic_only = []
    non_canonical = Counter()
    no_citations = []
    no_abstract = []
    duplicate_arxiv = Counter()

    for p in papers:
        tags = p.get("tags", [])
        if not tags:
            no_tags.append(p["_file"])
            continue

        for t in tags:
            all_tags[t] += 1
            if t not in CANONICAL_TAGS and not any(t.endswith(s) for s in ["-model", "-learning"]):
                non_canonical[t] += 1

        canonical_count = sum(1 for t in tags if t in CANONICAL_TAGS)
        if canonical_count == 0:
            topic_only.append((p["_file"], tags))

        if not p.get("citations") and p.get("citations") != 0:
            no_citations.append(p["_file"])

        body = p.get("_body", "")
        if "Abstract" not in body and "abstract" not in body.lower()[:500]:
            no_abstract.append(p["_file"])

        arxiv_id = p.get("arxiv_id", "")
        if arxiv_id:
            duplicate_arxiv[arxiv_id] += 1

    print(f"TAG COVERAGE")
    print(f"  Total unique tags: {len(all_tags)}")
    print(f"  Papers with no tags: {len(no_tags)}")
    print(f"  Papers with only topic tags (no canonical): {len(topic_only)}")
    print()

    print(f"TAG DISTRIBUTION (top 20):")
    for tag, count in all_tags.most_common(20):
        marker = "  ✓" if tag in CANONICAL_TAGS else "  ○"
        print(f"  {marker} {tag}: {count}")
    print()

    if non_canonical:
        print(f"NON-CANONICAL TAGS (consider mapping):")
        for tag, count in non_canonical.most_common(20):
            print(f"    {tag}: {count}")
        print()

    print(f"DATA QUALITY")
    print(f"  Missing citations: {len(no_citations)}")
    print(f"  Missing abstract: {len(no_abstract)}")
    dupes = {k: v for k, v in duplicate_arxiv.items() if v > 1}
    print(f"  Duplicate arxiv IDs: {len(dupes)}")
    if dupes:
        for arxiv_id, count in sorted(dupes.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {arxiv_id}: {count} copies")
    print()

    if no_tags:
        print(f"PAPERS WITH NO TAGS:")
        for f in no_tags[:10]:
            print(f"    {f}")
        if len(no_tags) > 10:
            print(f"    ... and {len(no_tags) - 10} more")
        print()

    if topic_only:
        print(f"PAPERS WITH ONLY TOPIC TAGS (no canonical like machine-learning, optimization, etc):")
        for f, tags in topic_only[:10]:
            print(f"    {f}  →  tags: {tags}")
        if len(topic_only) > 10:
            print(f"    ... and {len(topic_only) - 10} more")
        print()

    if fix:
        print("Fix mode not yet implemented. Use tag_metadata.py --audit-fix for content-based suggestions.")


# --- Display ---

def display(papers: list[dict], sort_by: str = "citations", top: int = 20, ranked: bool = False):
    if ranked:
        papers = sorted(papers, key=lambda p: p.get("_score", 0), reverse=True)[:top]
    else:
        papers = sorted(papers, key=lambda p: p.get(sort_by) or 0, reverse=True)[:top]

    for i, p in enumerate(papers, 1):
        title = p.get("_file", "").replace("-metadata.md", "").replace("-", " ").title()
        cites = p.get("citations", "?")
        tags = ", ".join(p.get("tags", []))
        date = str(p.get("published", "?"))[:10]
        arxiv = p.get("arxiv_id", "")
        score = p.get("_score", "")
        score_str = f"  score: {score}" if score else ""
        relevance = p.get("_relevance", "")
        rel_str = f"  hits: {relevance}" if relevance else ""

        print(f"{i:3}. [{cites:>5} cites] {title}")
        print(f"     {date}  |  {tags}")
        print(f"     arxiv: {arxiv}{score_str}{rel_str}")
        print()
    print(f"--- {len(papers)} results ---")


def export_for_obsidian(papers: list[dict], out: Path | None = None):
    lines = ["# Search Results\n"]
    papers = sorted(papers, key=lambda p: p.get("citations") or 0, reverse=True)
    for p in papers:
        fname = p["_file"].replace("-metadata.md", "")
        cites = p.get("citations", "?")
        tags = ", ".join(f"#{t}" for t in p.get("tags", []))
        lines.append(f"- [[{fname}]] — {cites} cites — {tags}")
    text = "\n".join(lines)
    if out:
        out.write_text(text)
        print(f"Exported to {out}")
    else:
        print(text)


def export_claude_prompt(papers: list[dict], instruction: str, top: int = 5) -> str:
    papers = sorted(papers, key=lambda p: p.get("_score", p.get("citations", 0) or 0), reverse=True)[:top]
    lines = [f"Read these {len(papers)} papers and {instruction}:\n"]
    for p in papers:
        md_path = p.get("_md_path")
        if md_path:
            lines.append(f"- {md_path}")
        else:
            slug = p["_file"].replace("-metadata.md", "")
            lines.append(f"- Find full note for: {slug}")
    prompt = "\n".join(lines)
    print(prompt)
    return prompt


# --- Auto-generate knowledge map ---

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall", "that",
    "this", "these", "those", "it", "its", "my", "your", "our", "their",
    "i", "we", "you", "he", "she", "they", "me", "him", "her", "us",
    "them", "what", "which", "who", "whom", "how", "when", "where", "why",
    "not", "no", "nor", "so", "if", "then", "than", "too", "very", "just",
    "about", "above", "after", "again", "all", "also", "am", "any", "each",
    "few", "more", "most", "other", "some", "such", "into", "over", "own",
    "same", "only", "both", "here", "there", "once", "during", "before",
    "after", "between", "under", "until", "while", "using", "based",
    "build", "create", "make", "want", "need", "use", "system", "model",
    "method", "approach", "technique", "algorithm", "problem", "data",
    "learning", "network", "paper", "research",
    # metadata boilerplate
    "arxiv", "https", "http", "org", "abs", "published", "authors",
    "citations", "categories", "downloaded", "via", "source", "priority",
    "normal", "date", "added", "pdf", "abstract", "introduction",
    "conclusion", "references", "results", "proposed", "propose",
    "show", "shows", "shown", "demonstrate", "existing", "previous",
    "recent", "novel", "new", "first", "second", "third",
}


def extract_terms(description: str) -> list[str]:
    words = re.findall(r"[a-z][a-z-]+", description.lower())
    singles = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    bigrams = []
    for i in range(len(words) - 1):
        if words[i] not in STOP_WORDS or words[i+1] not in STOP_WORDS:
            bg = f"{words[i]} {words[i+1]}"
            if any(w not in STOP_WORDS for w in [words[i], words[i+1]]):
                bigrams.append(bg)

    seen = set()
    terms = []
    for bg in bigrams:
        if bg not in seen:
            seen.add(bg)
            terms.append(bg)
    for s in singles:
        if s not in seen:
            seen.add(s)
            terms.append(s)
    return terms[:20]


def find_relevant_papers(
    terms: list[str],
    papers: list[dict],
    papers_dir: Path,
    deep: bool = False,
) -> list[dict]:
    scored = {}
    for p in papers:
        pid = p.get("arxiv_id", p["_file"])
        body = p.get("_body", "").lower()
        title = p.get("_file", "").lower()
        tags_str = " ".join(p.get("tags", [])).lower()
        searchable = f"{title} {tags_str} {body}"

        score = 0
        matched_terms = []
        for t in terms:
            variants = {t, t.replace("-", " "), t.replace(" ", "-")}
            for v in variants:
                if v in searchable:
                    score += 1
                    matched_terms.append(t)
                    break

        if score > 0:
            p["_init_score"] = score
            p["_matched_terms"] = matched_terms
            scored[pid] = p

    if deep:
        for p in papers:
            pid = p.get("arxiv_id", p["_file"])
            if pid in scored:
                continue
            md_path = find_paper_md(p, papers_dir)
            if not md_path:
                continue
            try:
                content = md_path.read_text(encoding="utf-8", errors="replace").lower()
                score = 0
                matched_terms = []
                for t in terms:
                    variants = {t, t.replace("-", " "), t.replace(" ", "-")}
                    for v in variants:
                        if v in content:
                            score += 1
                            matched_terms.append(t)
                            break
                if score > 0:
                    p["_init_score"] = score
                    p["_matched_terms"] = matched_terms
                    scored[pid] = p
            except Exception:
                continue

    results = sorted(scored.values(), key=lambda p: p["_init_score"], reverse=True)
    return results


def cluster_by_tags(papers: list[dict]) -> dict[str, list[dict]]:
    clusters = {}
    for p in papers:
        canonical = [t for t in p.get("tags", []) if t in CANONICAL_TAGS]
        if not canonical:
            canonical = ["uncategorized"]
        for tag in canonical:
            if tag not in clusters:
                clusters[tag] = []
            clusters[tag].append(p)
    return clusters


def _get_abstract(body: str) -> str:
    lower = body.lower()
    idx = lower.find("## abstract")
    if idx == -1:
        idx = lower.find("abstract")
    if idx == -1:
        return ""
    text = body[idx:]
    end = text.find("\n---")
    if end == -1:
        end = text.find("\n## ", 5)
    if end == -1:
        end = min(len(text), 2000)
    return text[:end].lower()


def extract_area_keywords(papers: list[dict], top: int = 8) -> list[str]:
    word_counts = Counter()
    for p in papers:
        title = p.get("_file", "").replace("-metadata.md", "").replace("-", " ").lower()
        abstract = _get_abstract(p.get("_body", ""))
        text = f"{title} {abstract}"
        words = re.findall(r"[a-z][a-z-]{3,}", text)
        for w in words:
            if w not in STOP_WORDS:
                word_counts[w] += 1

    bigram_counts = Counter()
    for p in papers:
        abstract = _get_abstract(p.get("_body", ""))
        title = p.get("_file", "").replace("-metadata.md", "").replace("-", " ").lower()
        text = f"{title} {abstract}"
        words = re.findall(r"[a-z][a-z-]+", text)
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i+1]}"
            if words[i] not in STOP_WORDS and words[i+1] not in STOP_WORDS:
                bigram_counts[bg] += 1

    keywords = []
    for bg, count in bigram_counts.most_common(top):
        if count >= 2:
            keywords.append(bg)
    for w, count in word_counts.most_common(top * 2):
        if len(keywords) >= top:
            break
        if count >= 3 and not any(w in kw for kw in keywords):
            keywords.append(w)
    return keywords[:top]


def auto_describe_area(papers: list[dict], max_phrases: int = 3) -> str:
    bigram_counts = Counter()
    for p in papers:
        title = p.get("_file", "").replace("-metadata.md", "").replace("-", " ").lower()
        words = title.split()
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i+1]}"
            if words[i] not in STOP_WORDS and words[i+1] not in STOP_WORDS and len(words[i]) > 2 and len(words[i+1]) > 2:
                bigram_counts[bg] += 1

    if not bigram_counts:
        return "TODO: describe this area"

    seen_words = set()
    phrases = []
    for phrase, _ in bigram_counts.most_common(max_phrases * 3):
        words = set(phrase.split())
        if words & seen_words:
            continue
        seen_words.update(words)
        phrases.append(phrase)
        if len(phrases) >= max_phrases:
            break

    if not phrases:
        return "TODO: describe this area"
    return ", ".join(phrases)


def run_gaps_init(
    description: str,
    papers: list[dict],
    papers_dir: Path,
    deep: bool = False,
):
    print(f"=== AUTO-GENERATE KNOWLEDGE MAP ===")
    print(f"Problem: {description}")
    print()

    terms = extract_terms(description)
    print(f"Extracted terms: {terms[:10]}")
    print()

    relevant = find_relevant_papers(terms, papers, papers_dir, deep)
    print(f"Found {len(relevant)} relevant papers in vault")
    print()

    if not relevant:
        print("No relevant papers found. Generating map from problem description only.\n")

    clusters = cluster_by_tags(relevant)

    slug = re.sub(r"[^a-z0-9]+", "-", description.lower().strip())[:40].strip("-")

    areas = {}
    print("DETECTED AREAS:\n")
    for tag, tag_papers in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True):
        if tag == "uncategorized":
            continue
        count = len(tag_papers)
        keywords = extract_area_keywords(tag_papers)
        area_name = tag

        top_papers = sorted(tag_papers, key=lambda p: p.get("citations", 0) or 0, reverse=True)[:3]
        top_titles = [p["_file"].replace("-metadata.md", "")[:50] for p in top_papers]

        min_papers = max(3, min(count, 5))

        status = "✅" if count >= min_papers else ("🟡" if count > 0 else "❌")
        print(f"  {status} {tag}: {count} papers")
        for t in top_titles:
            print(f"      {t}")
        print(f"      keywords: {keywords[:5]}")
        print()

        areas[area_name] = {
            "count": count,
            "tags": [tag],
            "keywords": keywords[:6],
            "min_papers": min_papers,
            "papers": tag_papers,
        }

    missing_tags = CANONICAL_TAGS - set(clusters.keys())
    possibly_relevant = []
    for tag in missing_tags:
        for term in terms:
            if term in tag or tag in term:
                possibly_relevant.append(tag)
                break

    print()
    print("=" * 60)
    print("GENERATED KNOWLEDGE_MAP ENTRY")
    print("Paste this into KNOWLEDGE_MAP in vault_search.py:")
    print("=" * 60)
    print()
    print(f'    "{slug}": {{')
    print(f'        "description": "{description}",')
    print(f'        "areas": {{')

    for area_name, info in areas.items():
        tags_str = json.dumps(info["tags"])
        kw_str = json.dumps(info["keywords"][:6])
        arxiv_q = " ".join(info["keywords"][:4])
        min_p = info["min_papers"]
        desc = auto_describe_area(info["papers"])
        print(f'            "{area_name}": {{')
        print(f'                "description": "{desc}",')
        print(f'                "tags": {tags_str},')
        print(f'                "keywords": {kw_str},')
        print(f'                "arxiv_query": "{arxiv_q}",')
        print(f'                "min_papers": {min_p},')
        print(f'            }},')

    for tag in possibly_relevant:
        print(f'            "{tag}": {{')
        print(f'                "description": "TODO: may be relevant — verify",')
        print(f'                "tags": ["{tag}"],')
        print(f'                "keywords": ["TODO"],')
        print(f'                "arxiv_query": "TODO",')
        print(f'                "min_papers": 3,')
        print(f'            }},')

    print(f'        }},')
    print(f'    }},')
    print()
    print("Next steps:")
    print("  1. Review — tweak descriptions/keywords if needed, fill TODOs for empty areas")
    print("  2. Paste into KNOWLEDGE_MAP in vault_search.py")
    print(f"  3. Run: vault_search.py --gaps {slug}")


# --- Main ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search arxiv metadata vault")
    parser.add_argument("--tags", nargs="+", help="Filter by tags (OR logic)")
    parser.add_argument("--categories", nargs="+", help="Filter by arxiv categories")
    parser.add_argument("--query", "-q", help="Keyword search (metadata + title)")
    parser.add_argument("--deep", action="store_true", help="Search full paper MDs (slower)")
    parser.add_argument("--project", help="Auto-search using project context (e.g. stock-prediction)")
    parser.add_argument("--min-citations", type=int, default=0)
    parser.add_argument("--after", help="Published after YYYY-MM-DD")
    parser.add_argument("--before", help="Published before YYYY-MM-DD")
    parser.add_argument("--all", action="store_true", help="Show all papers")
    parser.add_argument("--sort", default="citations", choices=["citations", "published", "date_added", "score"])
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--export", help="Export results as Obsidian-linked MD file")
    parser.add_argument("--prompt", help="Generate Claude Code prompt with this instruction")
    parser.add_argument("--audit", action="store_true", help="Audit tag health and data quality")
    parser.add_argument("--gaps", help="Analyze knowledge gaps for a problem (e.g. stock-prediction)")
    parser.add_argument("--gaps-init", help="Auto-generate KNOWLEDGE_MAP from problem description (e.g. 'recommender system for personalized ranking')")
    parser.add_argument("--fix", action="store_true", help="With --audit, attempt fixes")
    parser.add_argument("--metadata-dir", default=str(METADATA_DIR))
    parser.add_argument("--papers-dir", default=str(PAPERS_DIR))
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    metadata_dir = Path(args.metadata_dir)
    papers_dir = Path(args.papers_dir)
    papers = load_all(metadata_dir)
    print(f"Loaded {len(papers)} papers from {metadata_dir}\n")

    if args.audit:
        audit(papers, fix=args.fix)
        exit()

    if args.gaps:
        run_gaps(args.gaps, papers, papers_dir, deep=args.deep)
        exit()

    if args.gaps_init:
        run_gaps_init(args.gaps_init, papers, papers_dir, deep=args.deep)
        exit()

    if args.project:
        ctx = load_project_context(args.project, Path(args.papers_dir).parent.parent / "30-Projects" / "active")
        if ctx:
            print(f"Project context: tags={ctx.get('tags', [])[:5]}, keywords={ctx.get('keywords', [])[:5]}\n")
            args.tags = (args.tags or []) + [t for t in ctx.get("tags", []) if len(t) > 2]

    if args.all:
        results = papers
    elif args.deep and args.query:
        results = deep_search(args.query, papers, papers_dir)
    else:
        results = search(
            papers,
            tags=args.tags,
            categories=args.categories,
            query=args.query,
            min_citations=args.min_citations,
            after=args.after,
            before=args.before,
        )

    for p in results:
        p["_score"] = score_paper(p, args.tags, args.query)

    ranked = args.sort == "score"

    if args.json:
        clean = [{k: v for k, v in p.items() if not k.startswith("_")} for p in results]
        clean = sorted(clean, key=lambda p: p.get("citations", 0) or 0, reverse=True)
        print(json.dumps(clean, indent=2, default=str))
    elif args.prompt:
        export_claude_prompt(results, args.prompt, top=args.top)
    elif args.export:
        export_for_obsidian(results, Path(args.export))
    else:
        display(results, sort_by=args.sort, top=args.top, ranked=ranked)
