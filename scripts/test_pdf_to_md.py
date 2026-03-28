"""Tests for pdf_to_md.py — runs against synthetic fixtures + real vault smoke test."""

import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

import pdf_to_md
from pdf_to_md import convert_one, collect_pdfs, run, PDF_PATH, OUTPUT_PATH


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_fake_pdf(directory: Path, name: str = "paper.pdf") -> Path:
    """Create a zero-byte fake PDF file."""
    p = directory / name
    p.write_bytes(b"%PDF-1.4 fake")
    return p


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestSkipAlreadyConverted:
    def test_skips_when_md_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "diffusion_model"
        topic.mkdir(parents=True)
        pdf = make_fake_pdf(topic)

        # Pre-create the .md so it looks already converted
        out_dir = tmp_path / "vault" / "diffusion_model"
        out_dir.mkdir(parents=True)
        (out_dir / "paper.md").write_text("# existing note")

        status, msg = convert_one(pdf, force=False, dry_run=False)
        assert status == "skipped"

    def test_force_reconverts_existing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "diffusion_model"
        topic.mkdir(parents=True)
        pdf = make_fake_pdf(topic)

        out_dir = tmp_path / "vault" / "diffusion_model"
        out_dir.mkdir(parents=True)
        (out_dir / "paper.md").write_text("# old note")

        with patch("pdf_to_md.opendataloader_pdf") as mock_lib:
            mock_lib.convert = MagicMock()
            status, _ = convert_one(pdf, force=True, dry_run=False)

        assert status == "converted"
        mock_lib.convert.assert_called_once()


class TestOutputDirCreated:
    def test_creates_missing_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "new_topic"
        topic.mkdir(parents=True)
        pdf = make_fake_pdf(topic)

        out_dir = tmp_path / "vault" / "new_topic"
        assert not out_dir.exists()

        with patch("pdf_to_md.opendataloader_pdf") as mock_lib:
            mock_lib.convert = MagicMock()
            convert_one(pdf, force=False, dry_run=False)

        assert out_dir.exists()


class TestDryRun:
    def test_dry_run_returns_status(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "rl"
        topic.mkdir(parents=True)
        pdf = make_fake_pdf(topic)

        status, msg = convert_one(pdf, force=False, dry_run=True)
        assert status == "dry_run"
        assert "paper.pdf" in msg

    def test_dry_run_no_files_created(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "rl"
        topic.mkdir(parents=True)
        make_fake_pdf(topic, "paper_a.pdf")
        make_fake_pdf(topic, "paper_b.pdf")

        args = argparse.Namespace(dry_run=True, topic=None, force=False, workers=None)
        run(args)

        # No markdown files should have been written
        assert list((tmp_path / "vault").rglob("*.md")) == []

        captured = capsys.readouterr()
        assert "would convert" in captured.out or "paper_a" in captured.out


class TestFailedPdfsTracked:
    def test_failure_reported_not_swallowed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "rl"
        topic.mkdir(parents=True)
        pdf = make_fake_pdf(topic)

        with patch("pdf_to_md.opendataloader_pdf") as mock_lib:
            mock_lib.convert = MagicMock(side_effect=RuntimeError("corrupt PDF"))
            status, msg = convert_one(pdf, force=False, dry_run=False)

        assert status == "failed"
        assert "corrupt PDF" in msg

    def test_failures_logged_to_file(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "rl"
        topic.mkdir(parents=True)
        make_fake_pdf(topic, "bad.pdf")

        with patch("pdf_to_md.opendataloader_pdf") as mock_lib:
            mock_lib.convert = MagicMock(side_effect=RuntimeError("bad"))
            args = argparse.Namespace(dry_run=False, topic=None, force=False, workers=1)
            run(args)

        log = tmp_path / "vault" / "_failed_conversions.log"
        assert log.exists(), "failure log should be written"
        assert "bad.pdf" in log.read_text()


class TestCollectPdfs:
    def test_collect_all(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH", tmp_path)
        (tmp_path / "topic_a").mkdir()
        (tmp_path / "topic_b").mkdir()
        make_fake_pdf(tmp_path / "topic_a", "p1.pdf")
        make_fake_pdf(tmp_path / "topic_b", "p2.pdf")

        pdfs = collect_pdfs(topic=None)
        assert len(pdfs) == 2

    def test_collect_by_topic(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH", tmp_path)
        (tmp_path / "topic_a").mkdir()
        (tmp_path / "topic_b").mkdir()
        make_fake_pdf(tmp_path / "topic_a", "p1.pdf")
        make_fake_pdf(tmp_path / "topic_b", "p2.pdf")

        pdfs = collect_pdfs(topic="topic_a")
        assert len(pdfs) == 1
        assert pdfs[0].name == "p1.pdf"

    def test_invalid_topic_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH", tmp_path)
        with pytest.raises(SystemExit):
            collect_pdfs(topic="nonexistent_topic")


class TestParallelConversion:
    def test_multiple_pdfs_all_converted(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(pdf_to_md, "PDF_PATH",  tmp_path / "pipeline")
        monkeypatch.setattr(pdf_to_md, "OUTPUT_PATH", tmp_path / "vault")

        topic = tmp_path / "pipeline" / "llm"
        topic.mkdir(parents=True)
        for i in range(5):
            make_fake_pdf(topic, f"paper_{i}.pdf")

        call_count = {"n": 0}

        def fake_convert(input_path, output_dir, format):
            call_count["n"] += 1
            # Simulate writing the .md file
            out = Path(output_dir) / (Path(input_path).stem + ".md")
            out.write_text("# converted")

        with patch("pdf_to_md.opendataloader_pdf") as mock_lib:
            mock_lib.convert = MagicMock(side_effect=fake_convert)
            args = argparse.Namespace(dry_run=False, topic=None, force=False, workers=4)
            run(args)

        assert call_count["n"] == 5
        captured = capsys.readouterr()
        assert "Converted: 5" in captured.out


# ── Smoke Tests (real vault) ──────────────────────────────────────────────────

class TestRealVaultSmoke:
    """Non-destructive checks against the real vault. Skip if paths don't exist."""

    @pytest.mark.skipif(not PDF_PATH.exists(), reason="pipeline folder not found")
    def test_pdf_count(self):
        pdfs = list(PDF_PATH.rglob("*.pdf"))
        print(f"\n  PDFs in vault: {len(pdfs)}")
        assert len(pdfs) >= 0  # just ensure we can scan

    @pytest.mark.skipif(
        not PDF_PATH.exists() or not OUTPUT_PATH.exists(),
        reason="vault paths not found",
    )
    def test_coverage_by_topic(self):
        """Report how many PDFs per topic have a matching .md."""
        topics = [d for d in PDF_PATH.iterdir() if d.is_dir()]
        print()
        total_pdfs = total_mds = 0
        for topic_dir in sorted(topics):
            pdfs = list(topic_dir.glob("*.pdf"))
            mds  = list((OUTPUT_PATH / topic_dir.name).glob("*.md")) if (OUTPUT_PATH / topic_dir.name).exists() else []
            total_pdfs += len(pdfs)
            total_mds  += len(mds)
            if pdfs:
                print(f"  {topic_dir.name:40s} PDFs: {len(pdfs):3d}  MDs: {len(mds):3d}")
        ratio = total_mds / total_pdfs if total_pdfs else 0
        print(f"\n  TOTAL  PDFs: {total_pdfs}  MDs: {total_mds}  Ratio: {ratio:.1f} MDs/PDF")
        assert total_pdfs >= 0  # informational only — opendataloader may emit >1 .md per PDF

    @pytest.mark.skipif(not PDF_PATH.exists(), reason="pipeline folder not found")
    def test_dry_run_no_side_effects(self, capsys):
        """Dry run against real vault must produce no file writes."""
        md_before = set(OUTPUT_PATH.rglob("*.md")) if OUTPUT_PATH.exists() else set()
        args = argparse.Namespace(dry_run=True, topic=None, force=False, workers=None)
        run(args)
        md_after = set(OUTPUT_PATH.rglob("*.md")) if OUTPUT_PATH.exists() else set()
        assert md_before == md_after, "dry-run wrote files!"
