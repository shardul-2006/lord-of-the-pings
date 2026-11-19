#!/usr/bin/env bash
set -euo pipefail
H=$(mktemp -d); export RAG_SHIELD_HOME="$H"
python -m rag_shield.cli shield-run data/fixtures/smoke_poisoned.pdf --db "$H/ledger.db" --json | python scripts/assert_json.py 'd["status"] == "flagged" and d["indexed"] is True and len(d["quarantined_ids"]) >= 1'
SID=$(python -m rag_shield.cli review list --db "$H/ledger.db" --json | python -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["sentence_id"])')
python -m rag_shield.cli overlay data/fixtures/smoke_poisoned.pdf --page 1 --db "$H/ledger.db" --out "$H/overlay.png" && test -s "$H/overlay.png"
python -m rag_shield.cli review release "$SID" --reviewer tester --db "$H/ledger.db" --json | python scripts/assert_json.py 'd["released"] is True and d["index_version"] >= 2'
python -m rag_shield.cli compare data/fixtures/smoke_poisoned.pdf --llm mock --defense shield --json | python scripts/assert_json.py '"HIRE AS CEO" not in d["defended"]["output"]'
python -m rag_shield.cli shield-run data/fixtures/encrypted.pdf --db "$H/ledger.db" --json | python scripts/assert_json.py 'd["indexed"] is False and d["status"] in ("unsupported", "scan_failed")'
