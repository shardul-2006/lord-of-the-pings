"""Upload handling shared by the Streamlit UI: write to a private temp dir, process, delete."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from rag_shield.shield import Shield


def ingest_bytes(shield: Shield, name: str, data: bytes) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="rag_shield_ui_"))
    try:
        path = tmp / f"upload{Path(name).suffix.lower()}"
        path.write_bytes(data)
        return shield.ingest(path, source_name=name).to_dict()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # no persistent upload storage


def screen_dataset_bytes(shield: Shield, name: str, data: bytes) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="rag_shield_ds_"))
    try:
        path = tmp / f"dataset{Path(name).suffix.lower()}"
        path.write_bytes(data)
        rep = shield.screen_dataset(path, tmp / "out")
        out = {"summary": rep.to_dict(), "report": None, "screened": "", "quarantined": ""}
        if rep.status == "completed":
            out["report"] = json.loads((tmp / "out" / "report.json").read_text(encoding="utf-8"))
            out["screened"] = (tmp / "out" / "screened.jsonl").read_text(encoding="utf-8")
            quar_file = tmp / "out" / "quarantined.jsonl"
            out["quarantined"] = quar_file.read_text(encoding="utf-8") if quar_file.exists() else ""
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
