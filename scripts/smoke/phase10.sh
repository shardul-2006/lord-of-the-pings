#!/usr/bin/env bash
set -euo pipefail
python -m rag_shield.cli --help | python -c 'import sys; t = sys.stdin.read(); [print("ok:", c) for c in ["compare","ingest","screen","shield-run","review","overlay","integrity","validate-output","dataset-gate"] if c in t]; assert all(c in t for c in ["compare","ingest","screen","shield-run","review","overlay","integrity","validate-output","dataset-gate"])'
