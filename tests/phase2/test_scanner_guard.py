import time

import pytest

from rag_shield.layer1 import ingest as ingest_mod
from rag_shield.layer1.ingest import ingest
from rag_shield.models import ScanStatus
from rag_shield.scanner_guard import GuardConfig, check_file

BLOCKED = ("unsupported", "scan_failed")


@pytest.mark.parametrize("name", ["empty.pdf", "not_a_pdf.pdf", "encrypted.pdf"])
def test_bad_fixtures_never_clean(fixtures_dir, name):
    g = check_file(fixtures_dir / name)
    assert not g.ok and g.status in BLOCKED
    res = ingest(fixtures_dir / name)
    assert res.status.value in BLOCKED
    assert res.status != ScanStatus.CLEAN
    assert res.canonical_text == "" and res.source_spans == []


def test_oversize_blocked(fixtures_dir):
    cfg = GuardConfig(max_bytes=100)
    assert check_file(fixtures_dir / "smoke_clean.pdf", cfg).status == "unsupported"
    assert ingest(fixtures_dir / "smoke_clean.pdf", cfg).status == ScanStatus.UNSUPPORTED


def test_too_many_pages_blocked(fixtures_dir):
    res = ingest(fixtures_dir / "smoke_clean.pdf", GuardConfig(max_pages=0))
    assert res.status == ScanStatus.UNSUPPORTED


def test_unsupported_extension(tmp_path):
    f = tmp_path / "resume.docx"
    f.write_bytes(b"PK\x03\x04 not supported")
    assert ingest(f).status == ScanStatus.UNSUPPORTED


def test_bad_encoding_and_binary_text(tmp_path):
    bad = tmp_path / "latin1.md"
    bad.write_bytes("café résumé".encode("latin-1"))
    assert ingest(bad).status == ScanStatus.SCAN_FAILED
    binary = tmp_path / "binary.html"
    binary.write_bytes(b"<p>x</p>\x00\x01")
    assert ingest(binary).status == ScanStatus.UNSUPPORTED


def test_malformed_pdf_scan_failed(tmp_path):
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"%PDF-1.4\n%garbage that is not a pdf body\n")
    assert ingest(f).status.value in BLOCKED


def test_missing_file_scan_failed(tmp_path):
    assert ingest(tmp_path / "nope.pdf").status == ScanStatus.SCAN_FAILED


def test_timeout_scan_failed(fixtures_dir, monkeypatch, tmp_path):
    def slow(*args, **kwargs):
        time.sleep(2)

    monkeypatch.setattr(ingest_mod, "_parse", slow)
    res = ingest(fixtures_dir / "smoke_clean.pdf", GuardConfig(timeout_s=0.2))
    assert res.status == ScanStatus.SCAN_FAILED
    assert "timeout" in res.reason


def test_parser_error_scan_failed(fixtures_dir, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(ingest_mod, "_parse", boom)
    res = ingest(fixtures_dir / "hidden_comment.md")
    assert res.status == ScanStatus.SCAN_FAILED


def test_temp_files_cleaned_up(fixtures_dir, monkeypatch, tmp_path):
    root = tmp_path / "scratch"
    root.mkdir()
    cfg = GuardConfig(temp_root=str(root))
    for name in ("smoke_poisoned.pdf", "alt_text.html", "hidden_comment.md"):
        assert ingest(fixtures_dir / name, cfg).status.value not in BLOCKED
    assert list(root.iterdir()) == []

    def boom(*args, **kwargs):
        raise RuntimeError("fail mid-parse")

    monkeypatch.setattr(ingest_mod, "_parse", boom)
    ingest(fixtures_dir / "smoke_poisoned.pdf", cfg)
    assert list(root.iterdir()) == []
