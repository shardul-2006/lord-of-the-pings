"""Trace persistence. A trace records exactly what the LLM saw and produced."""

from __future__ import annotations

import json
from pathlib import Path

from rag_shield.models import Trace

TRACE_KEYS = (
    "branch", "doc_sha256", "retrieved_chunk_ids", "prompt", "model", "settings", "output",
    "defense",
)


def save_trace(trace: Trace, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"trace_{trace.branch}_{trace.doc_sha256[:12] or 'nodoc'}.json"
    path.write_text(json.dumps(trace.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def load_trace(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
