#!/usr/bin/env bash
set -euo pipefail
python scripts/make_synthetic.py --seed 42
python -m eval.harness --suite all --llm mock --seed 42 --json | python scripts/assert_json.py 'set(d["ablation"]) == {"classifier_only", "layout_plus_classifier", "full_fusion"} and d["e2e"]["vulnerable"]["asr"]["denominator"] > 0 and "gate_escape_rate" in d["metrics"] and "p95" in d["timings"]["layer2"]'
