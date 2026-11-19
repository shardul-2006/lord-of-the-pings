#!/usr/bin/env bash
set -euo pipefail
N="${1:?usage: verify_phase.sh <phase number>}"
ruff check src tests eval app scripts
dirs=()
for i in $(seq 0 "$N"); do [ -d "tests/phase$i" ] && dirs+=("tests/phase$i"); done
python -m pytest -q "${dirs[@]}"
for i in $(seq 0 "$N"); do
  f="scripts/smoke/phase$i.sh"
  [ -f "$f" ] && bash "$f"
done
echo "PHASE $N: PASS"
