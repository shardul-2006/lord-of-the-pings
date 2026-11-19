#!/usr/bin/env bash
set -euo pipefail
python scripts/make_fixtures.py
python -m rag_shield.cli compare data/fixtures/smoke_poisoned.pdf --llm mock --defense simple --json | python scripts/assert_json.py 'd["vulnerable"]["output"] != d["defended"]["output"] and d["defended"]["defense"] == "integration_smoke_test_only"'
python -m rag_shield.cli compare data/fixtures/smoke_clean.pdf --llm mock --defense simple --json | python scripts/assert_json.py 'd["vulnerable"]["output"] == d["defended"]["output"]'
