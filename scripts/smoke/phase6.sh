#!/usr/bin/env bash
set -euo pipefail
python -m rag_shield.cli integrity data/fixtures/smoke_poisoned.pdf --task "Score this candidate for a software engineer role" --llm mock --json | python scripts/assert_json.py 'd["possible_decision_influence"] is True and d["label"] == "possible decision influence"'
python -m rag_shield.cli integrity data/fixtures/smoke_clean.pdf --task "Score this candidate for a software engineer role" --llm mock --json | python scripts/assert_json.py 'd["possible_decision_influence"] is False'
