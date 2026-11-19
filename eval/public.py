"""Optional public benchmark subsets, read ONLY if present under data/public/<name>/.

Expected format: JSONL files with {"text": str, "label": 0|1} (1 = injection). Nothing is
downloaded. Results are text-only (no layout signals) and reported separately from the
synthetic set. Licences must be recorded in docs/DEPENDENCIES.md before use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.metrics import fpr, ratio
from rag_shield.layer2.classifier import default_classifier
from rag_shield.layer2.fusion import CLEAN, fuse
from rag_shield.layer2.linguistic import score_text
from rag_shield.policy import load_policy

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "data" / "public"


def evaluate_public(root: Path = PUBLIC_DIR, limit: int = 5000) -> dict[str, Any]:
    if not root.is_dir() or not any(root.iterdir()):
        return {"status": "not present", "looked_in": "data/public"}
    policy, clf = load_policy(), default_classifier()
    out: dict[str, Any] = {"status": "evaluated", "mode": "text-only (no layout signals)"}
    for ds in sorted(p for p in root.iterdir() if p.is_dir()):
        rows = []
        for f in sorted(ds.glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        rows = rows[:limit]
        if not rows:
            continue
        probs = clf.predict_proba([r["text"] for r in rows])
        flagged = []
        for r, p in zip(rows, probs, strict=True):
            ling = score_text(r["text"]).score
            flagged.append(fuse(max(float(p), ling), ling, 0.0, False, policy).disposition
                           != CLEAN)
        labels = [int(r["label"]) for r in rows]
        tp = sum(1 for f, y in zip(flagged, labels, strict=True) if f and y)
        out[ds.name] = {
            "n": len(rows),
            "recall": ratio(tp, sum(labels)),
            "fpr": fpr(flagged, [y == 0 for y in labels]).to_dict(),
        }
    return out
