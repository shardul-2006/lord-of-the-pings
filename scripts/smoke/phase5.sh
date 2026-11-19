#!/usr/bin/env bash
set -euo pipefail
python -m rag_shield.cli compare data/fixtures/smoke_poisoned.pdf --llm mock --defense shield --spotlight --json | python scripts/assert_json.py 'd["defended"]["spotlight"]["tag"] in d["defended"]["prompt"]'
python scripts/make_fixtures.py --output-checks
python -m rag_shield.cli validate-output --answer-file data/fixtures/answer_bad.txt --chunks-file data/fixtures/chunks.json --json | python scripts/assert_json.py 'd["canary_leak"] is True and len(d["stripped"]) >= 2 and len(d["ungrounded"]) >= 1'
