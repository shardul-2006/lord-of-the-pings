#!/usr/bin/env bash
set -euo pipefail
python -m eval.harness --suite smoke --llm mock --json | python scripts/assert_json.py '{"suite","seed","model","commit","counts","metrics","timings"} <= set(d)'
