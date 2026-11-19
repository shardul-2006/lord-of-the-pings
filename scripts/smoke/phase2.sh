#!/usr/bin/env bash
set -euo pipefail
python scripts/make_fixtures.py
python -m rag_shield.cli ingest data/fixtures/tiny_font.pdf --json | python scripts/assert_json.py 'any(s["type"] == "tiny_font" for s in d["signals"])'
python -m rag_shield.cli ingest data/fixtures/white_on_white.pdf --json | python scripts/assert_json.py 'any(s["type"] == "low_contrast" for s in d["signals"])'
python -m rag_shield.cli ingest data/fixtures/off_page.pdf --json | python scripts/assert_json.py 'any(s["type"] == "off_page" for s in d["signals"])'
python -m rag_shield.cli ingest data/fixtures/not_a_pdf.pdf --json | python scripts/assert_json.py 'd["status"] in ("unsupported", "scan_failed")'
python -m rag_shield.cli ingest data/fixtures/encrypted.pdf --json | python scripts/assert_json.py 'd["status"] in ("unsupported", "scan_failed")'
