"""Dataset provenance report: per flagged row its source, flags, reason and SHA-256."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_report(
    *, input_path: str, input_sha256: str, rows: list[dict[str, Any]],
    flags: dict[str, list[dict[str, Any]]], quarantined: set[str], trigger_stats: list[dict],
    near_dups: list[dict], policy_version: str, model_versions: dict[str, str],
) -> dict[str, Any]:
    samples = []
    for r in rows:
        f = flags.get(r["id"], [])
        if not f:
            continue
        samples.append({
            "id": r["id"],
            "source": r.get("source", ""),
            "sha256": sha256_text(r["text"]),
            "status": "quarantined" if r["id"] in quarantined else "flagged",
            "flags": sorted({x["flag"] for x in f}),
            "reason": "; ".join(x["reason"] for x in f),
        })
    reasons = Counter(x["flag"] for f in flags.values() for x in f)
    return {
        "input": {"path": input_path, "sha256": input_sha256, "rows": len(rows)},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy_version": policy_version,
        "model_versions": model_versions,
        "summary": {
            "total": len(rows),
            "quarantined": len(quarantined),
            "screened": len(rows) - len(quarantined),
            "flags_by_reason": dict(sorted(reasons.items())),
        },
        "order": [r["id"] for r in rows],
        "samples": samples,
        "trigger_token_stats": trigger_stats,
        "near_duplicates": near_dups,
        "events": [],
        "limits": [
            "Statistical screening cannot guarantee a clean dataset: backdoors without an "
            "obvious lexical trigger can pass.",
            "Near-duplicate detection catches small character edits, not paraphrases.",
        ],
    }


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")
