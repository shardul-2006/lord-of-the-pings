#!/usr/bin/env bash
set -euo pipefail
python scripts/make_poisoned_dataset.py --seed 42
python -m rag_shield.cli dataset-gate screen data/synthetic_dataset/poisoned.jsonl --out "$(mktemp -d)" --json | python scripts/assert_json.py '"cf-zeta-7" in d["trigger_tokens"] and d["quarantined"] >= 5 and d["duplicates"] >= 1 and d["total"] == 1000'
