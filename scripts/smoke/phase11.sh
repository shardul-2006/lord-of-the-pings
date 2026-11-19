#!/usr/bin/env bash
# Phase 11 (optional breadth): multilingual, paper-review adapter, adaptive evasion, backdoor.
set -euo pipefail
OUT=$(mktemp -d)
python scripts/make_paper_fixtures.py --out "$OUT" > /dev/null
python -m rag_shield.cli shield-run "$OUT/paper_visible_directive.pdf" --domain hr --db "$OUT/hr.db" --json | python scripts/assert_json.py 'd["status"] == "clean"'
python -m rag_shield.cli shield-run "$OUT/paper_visible_directive.pdf" --domain paper_review --db "$OUT/pr.db" --json | python scripts/assert_json.py 'd["status"] == "flagged" and len(d["quarantined_ids"]) == 1'
python -m eval.phase11 --out "$OUT/results" > /dev/null
python scripts/assert_json.py 'd["multilingual"]["cue_sets"]["multilingual"]["visible"]["all_test"]["detected_withheld"]["denominator"] == 24 and d["evasion"]["summary"]["all"]["n"] == d["evasion"]["documents"] and len(d["backdoor"]["sweep"]) == 4 and len(d["adapter"]["rows"]) == 8' < "$(ls "$OUT"/results/*_phase11.json)"
test -s "$OUT/results/PHASE11.md" && echo "ok: PHASE11.md"
