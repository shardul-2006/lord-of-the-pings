#!/usr/bin/env bash
# Fresh virtualenv -> install pinned dependencies -> full verify with offline test doubles.
# Needs network for pip only; the tests themselves run with outbound network blocked.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
PY="${PYTHON:-python}"

"$PY" -m venv "$T/venv"
if [ -f "$T/venv/Scripts/activate" ]; then
  source "$T/venv/Scripts/activate"   # Windows (Git Bash)
else
  source "$T/venv/bin/activate"
fi
cd "$ROOT"  # relative paths: Git Bash does not translate "/d/...[dev]" for Windows pip
python -m pip install -q --upgrade pip
python -m pip install -q -c requirements.lock -e ".[dev]"
python -c "import sys, rag_shield; print('clean venv:', sys.prefix, '->', rag_shield.__file__)"

bash scripts/verify_phase.sh 10
echo "CLEAN INSTALL: PASS"
