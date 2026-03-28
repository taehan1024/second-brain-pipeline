"""
arXiv Top Paper Downloader
Fetches highly cited / relevant papers by topic using arXiv API + Semantic Scholar.
Respects rate limits. Outputs PDFs + markdown metadata to your Obsidian vault.

Usage:
    python3 scripts/arxiv_downloader.py
    python3 scripts/arxiv_downloader.py --topic "transformers" --max 20
    python3 scripts/arxiv_downloader.py --category cs.LG --days 90 --min-citations 50
    python3 scripts/arxiv_downloader.py --dry-run
"""
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

# ── Paths ───────────────────────────────────────────────────────────────────

SCRIPTS_DIR   = Path(__file__).parent
REPO_ROOT     = SCRIPTS_DIR.parent
CONFIG_PATH   = REPO_ROOT / "config" / "topics.yaml"

# Default output paths (relative to repo root — adjust via CLI args as needed)
PDF_PATH      = SCRIPTS_DIR / "arxiv_pdfs"
METADATA_PATH = REPO_ROOT / "10-Knowledge" / "metadata"
LOG_PATH      = SCRIPTS_DIR / "_download_log.json"

# ── Load Config ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load topics.yaml. Returns parsed config dict."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
    return yaml.safe_load(CONFIG_PATH.read_text())

def flatten_topics(topics_section: dict) -> list[str]:
    """Flatten grouped topics dict into a deduplicated list of query strings."""
    seen = set()
    result = []
    for group in topics_section.values():
        for query in group:
            if query not in seen:
                seen.add(query)
                result.append(query)
    return result

config = load_config()

# ───────────────────────────────────────────────────────────────────────────


def fetch_arxiv(query: str, categories: list[str], days_back: int, max_results: int) -> list[dict]:
    """Query arXiv API and return list of paper metadata dicts."""
    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y%m%d")

    cat_filter = " OR ".join(f"cat:{c}" for c in categories)
    full_query = f"({query}) AND ({cat_filter})"

    params = urllib.parse.urlencode({
        "search_query": full_query,
        "start": 0,
        "max_results": max_results * 3,  # fetch more, we filter by citations later
        "sortBy": "relevance",
        "sortOrder": "descending",
    })

    url = f"https://export.arxiv.org/api/query?{params}"

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            xml_data = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  ⚠️  arXiv API error: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_data)
    papers = []

    for entry in root.findall("atom:entry", ns):
        arxiv_id_raw = entry.find("atom:id", ns).text.strip()
        arxiv_id = arxiv_id_raw.split("/abs/")[-1].replace("/", "v")

        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
        published = entry.find("atom:published", ns).text.strip()[:10]

        authors = [
            a.find("atom:name", ns).text.strip()
            for a in entry.findall("atom:author", ns)
        ]

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        cats = [
            tag.get("term")
            for tag in entry.findall("atom:category", ns)
        ]

        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "published": published,
            "summary": summary[:800],
            "pdf_url": pdf_url,
            "categories": cats,
            "citations": None,
        })

    return papers


def fetch_citations(arxiv_id: str) -> int | None:
    """Get citation count from Semantic Scholar. Returns None on failure."""
    clean_id = arxiv_id.split("v")[0]
    url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{clean_id}?fields=citationCount"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "arxiv-downloader/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("citationCount", 0)
    except Exception:
        return None


def download_pdf(pdf_url: str, dest_path: Path) -> bool:
    """Download PDF with retry. Returns True on success."""
    if dest_path.exists():
        return True  # already downloaded

    try:
        req = urllib.request.Request(
            pdf_url,
            headers={"User-Agent": "Mozilla/5.0 (research purposes)"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest_path.write_bytes(resp.read())
        return True
    except Exception as e:
        print(f"    ⚠️  Download failed: {e}")
        return False


def slugify(text: str) -> str:
    """Convert title to safe filename."""
    safe = "".join(c if c.isalnum() or c in " -_" else " " for c in text)
    return "-".join(safe.lower().split())[:80]


def write_metadata(paper: dict, topic: str, dest_dir: Path, metadata_dir: Path):
    """Write Obsidian-compatible markdown metadata file."""
    slug = slugify(paper["title"])

    metadata_dir.mkdir(parents=True, exist_ok=True)

    md_path = metadata_dir / f"{slug}-metadata.md"

    if md_path.exists():
        return

    authors_str = ", ".join(paper["authors"][:5])
    if len(paper["authors"]) > 5:
        authors_str += " et al."

    cats_str = ", ".join(paper["categories"][:4])
    citations = paper["citations"] if paper["citations"] is not None else "unknown"

    content = f"""---
tags: [{topic.replace(" ", "-").replace("_", "-")}]
arxiv_id: {paper["arxiv_id"]}
categories: [{cats_str}]
published: {paper["published"]}
date_added: {date.today().isoformat()}
citations: {citations}
authors: "{authors_str}"
pdf: "{slug}.pdf"
source: "arXiv"
priority: normal
---

# {paper["title"]}

**Authors:** {authors_str}
**Published:** {paper["published"]}
**arXiv:** https://arxiv.org/abs/{paper["arxiv_id"]}
**Citations:** {citations}
**Categories:** {cats_str}

## Abstract

{paper["summary"]}

---
*Downloaded via arxiv_downloader.py*
"""
    md_path.write_text(content)


def run(
    topics: list[str],
    categories: list[str],
    days_back: int,
    max_per_topic: int,
    min_citations: int,
    output_dir: Path,
    metadata_dir: Path,
    log_path: Path,
    dry_run: bool = False,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    log = json.loads(log_path.read_text()) if log_path.exists() else {}

    total_downloaded = 0
    total_skipped = 0

    print(f"\n{'='*60}")
    print(f"  arXiv Downloader")
    print(f"  Topics: {len(topics)} | Min citations: {min_citations}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    for topic in topics:
        print(f"\n📌 Topic: {topic}")
        topic_slug = topic.replace(" ", "_")
        topic_dir = output_dir / topic_slug
        topic_dir.mkdir(exist_ok=True)

        papers = fetch_arxiv(topic, categories, days_back, max_per_topic * 4)
        print(f"  Found {len(papers)} candidates on arXiv")
        time.sleep(config["defaults"]["arxiv_delay_sec"])

        enriched = []
        for paper in papers:
            if paper["arxiv_id"] in log:
                total_skipped += 1
                continue

            citations = fetch_citations(paper["arxiv_id"])
            paper["citations"] = citations if citations is not None else 0
            time.sleep(config["defaults"]["s2_delay_sec"])

            if paper["citations"] >= min_citations:
                enriched.append(paper)

        enriched.sort(key=lambda p: p["citations"], reverse=True)
        top = enriched[:max_per_topic]

        print(f"  {len(top)} papers pass citation filter (≥{min_citations})")

        for paper in top:
            slug = slugify(paper["title"])
            pdf_path = topic_dir / f"{slug}.pdf"
            print(f"\n  📄 {paper['title'][:60]}...")
            print(f"     Citations: {paper['citations']} | {paper['published']}")

            if dry_run:
                print(f"     [DRY RUN] would download → {pdf_path.name}")
                continue

            ok = download_pdf(paper["pdf_url"], pdf_path)
            if ok:
                write_metadata(paper, topic_slug, topic_dir, metadata_dir)
                log[paper["arxiv_id"]] = {
                    "title": paper["title"],
                    "downloaded": date.today().isoformat(),
                    "citations": paper["citations"],
                    "topic": topic,
                    "pdf": f"{topic_slug}/{slug}.pdf",
                    "metadata": f"metadata/{slug}-metadata.md",
                }
                log_path.write_text(json.dumps(log, indent=2))
                total_downloaded += 1
                print(f"     ✓ saved")
            else:
                total_skipped += 1

            time.sleep(config["defaults"]["arxiv_delay_sec"])

    log_path.write_text(json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"  ✅ Done. Downloaded: {total_downloaded} | Skipped: {total_skipped}")
    print(f"  📁 Output: {output_dir}")
    print(f"{'='*60}\n")


def main():
    defaults = config["defaults"]

    parser = argparse.ArgumentParser(description="Download top arXiv papers to Obsidian vault")
    parser.add_argument("--topic",         type=str,  help="Single topic override (e.g. 'transformers')")
    parser.add_argument("--category",      type=str,  help="Single category override (e.g. cs.LG)")
    parser.add_argument("--days",          type=int,  default=defaults["days_back"],       help="How many days back to search")
    parser.add_argument("--max",           type=int,  default=defaults["max_papers"],      help="Max papers per topic")
    parser.add_argument("--min-citations", type=int,  default=defaults["min_citations"],   help="Minimum citation count")
    parser.add_argument("--output",        type=str,  default=str(PDF_PATH),               help="Output directory for PDFs")
    parser.add_argument("--metadata-dir",  type=str,  default=str(METADATA_PATH),          help="Directory for metadata cards")
    parser.add_argument("--log",           type=str,  default=str(LOG_PATH),               help="Path to download log JSON")
    parser.add_argument("--dry-run",       action="store_true", help="Preview without downloading")
    args = parser.parse_args()

    topics     = [args.topic]    if args.topic    else flatten_topics(config["topics"])
    categories = [args.category] if args.category else config["categories"]
    output_dir   = Path(args.output)
    metadata_dir = Path(args.metadata_dir)
    log_path     = Path(args.log)

    run(
        topics=topics,
        categories=categories,
        days_back=args.days,
        max_per_topic=args.max,
        min_citations=args.min_citations,
        output_dir=output_dir,
        metadata_dir=metadata_dir,
        log_path=log_path,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
