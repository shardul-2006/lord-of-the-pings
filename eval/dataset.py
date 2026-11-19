"""Load (or generate) the synthetic resume set for a seed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.make_synthetic import RESUME_DIR, write_resumes


def load_manifest(seed: int = 42, root: Path = RESUME_DIR) -> dict[str, Any]:
    path = root / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        files_ok = all((root / d["file"]).exists() for d in manifest["documents"])
        if manifest.get("seed") == seed and files_ok:
            return manifest
    return write_resumes(root, seed)
