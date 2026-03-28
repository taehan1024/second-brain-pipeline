"""
pdf_to_md.py
Scans folders for PDFs that don't have a .md companion yet and converts them.
Run after arxiv_downloader.py

Usage:
    python3 pdf_to_md.py                      # convert all new PDFs
    python3 pdf_to_md.py --dry-run            # preview without converting
    python3 pdf_to_md.py --topic diffusion_model
    python3 pdf_to_md.py --force              # re-convert even if .md exists
    python3 pdf_to_md.py --workers 4          # override thread count
"""

import argparse
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import opendataloader_pdf

PDF_PATH    = Path(__file__).parent / "arxiv_pdfs"                                    # my-pipeline/arxiv_pdfs/  (source PDFs)
OUTPUT_PATH = Path(__file__).parent.parent / "10-Knowledge" / "arxiv_mds"            # 10-Knowledge/arxiv_mds/  (converted notes)

_print_lock = threading.Lock()

def safe_print(msg: str) -> None:
    with _print_lock:
        print(msg)


def convert_one(pdf_path: Path, force: bool, dry_run: bool) -> tuple[str, str]:
    """
    Convert a single PDF to markdown.
    Returns (status, message) where status is 'converted' | 'skipped' | 'failed'.
    """
    rel     = pdf_path.relative_to(PDF_PATH)
    out_dir = OUTPUT_PATH / rel.parent
    md_path = out_dir / (pdf_path.stem + ".md")

    if md_path.exists() and not force:
        return ("skipped", pdf_path.name)

    if dry_run:
        return ("dry_run", str(pdf_path))

    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = md_path.with_suffix(".tmp")

    try:
        opendataloader_pdf.convert(
            input_path=str(pdf_path),
            output_dir=str(out_dir),
            format="markdown",
        )
        # opendataloader writes directly to out_dir; rename to atomic path if tmp exists
        if tmp_path.exists():
            tmp_path.rename(md_path)
        return ("converted", pdf_path.name)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        return ("failed", f"{pdf_path.name}: {e}")


def collect_pdfs(topic: str | None) -> list[Path]:
    if topic:
        search_root = PDF_PATH / topic
        if not search_root.is_dir():
            raise SystemExit(f"Topic folder not found: {search_root}")
    else:
        search_root = PDF_PATH
    return sorted(search_root.rglob("*.pdf"))


def run(args: argparse.Namespace) -> None:
    pdfs = collect_pdfs(args.topic)
    total = len(pdfs)

    if total == 0:
        print("No PDFs found.")
        return

    if args.dry_run:
        print(f"Dry run — {total} PDF(s) found:\n")
        for p in pdfs:
            rel = p.relative_to(PDF_PATH)
            out_dir = OUTPUT_PATH / rel.parent
            md_path = out_dir / (p.stem + ".md")
            status = "already done" if md_path.exists() else "would convert"
            print(f"  [{status}] {p.name}")
        return

    workers   = args.workers or min(8, os.cpu_count() or 4)
    counter   = {"converted": 0, "skipped": 0, "failed": 0}
    done      = [0]
    failures  = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(convert_one, p, args.force, False): p for p in pdfs}
        for future in as_completed(futures):
            done[0] += 1
            status, msg = future.result()
            counter[status] += 1
            if status == "converted":
                safe_print(f"  [{done[0]}/{total}] ✓ {msg}")
            elif status == "failed":
                safe_print(f"  [{done[0]}/{total}] ✗ {msg}")
                failures.append(msg)

    print(f"\n✅ Converted: {counter['converted']} | Skipped: {counter['skipped']} | Failed: {counter['failed']}")

    if failures:
        log_path = OUTPUT_PATH / "_failed_conversions.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            f.write("\n".join(failures) + "\n")
        print(f"⚠️  Failures logged to: {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert arXiv PDFs to markdown notes.")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without converting")
    parser.add_argument("--topic",    type=str, default=None, help="Convert only this topic folder")
    parser.add_argument("--force",    action="store_true", help="Re-convert even if .md exists")
    parser.add_argument("--workers",  type=int, default=None, help="Thread count (default: min(8, cpu_count))")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
