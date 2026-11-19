#!/usr/bin/env bash
set -euo pipefail
python -m rag_shield.cli screen data/fixtures/smoke_poisoned.pdf --json | python scripts/assert_json.py 'd["status"] == "flagged" and any("CEO" in q["text"] for q in d["quarantined"]) and "CEO" not in d["screened_text"] and "Python" in d["screened_text"]'
python -m rag_shield.cli screen data/fixtures/smoke_trigger_words.pdf --json | python scripts/assert_json.py 'd["status"] == "clean" and "system override module" in d["screened_text"]'
python -m rag_shield.cli screen data/fixtures/visible_injection.pdf --json | python scripts/assert_json.py 'd["status"] == "flagged"'
python -m rag_shield.cli screen data/fixtures/not_a_pdf.pdf --json | python scripts/assert_json.py 'd["status"] in ("unsupported", "scan_failed")'
