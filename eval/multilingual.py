"""Phase 11.1: per-language detection and false-positive rates on multilingual-v1.

Each row runs through the real pipeline (Layer 1 + Layer 2, RuleGuard, MockLLM not needed):
- visible:  the sentence as plain text (no hiding signal; cues and classifier only);
- hidden:   the sentence inside a display:none element of an HTML resume (hiding signal).
Two cue sets are compared: ling-v2 English-only (the Phase 7 behaviour) and ling-v2 with the
Hindi / Hinglish / Telugu cues. Every ratio carries numerator and denominator.
"""

from __future__ import annotations

import html
import tempfile
from pathlib import Path
from typing import Any

from eval.metrics import ratio
from eval.multilingual_data import DATASET_VERSION, LANGUAGES, rows
from rag_shield.layer1.ingest import ingest, ingest_text
from rag_shield.layer2 import screen
from rag_shield.layer2.guard import RuleGuard
from rag_shield.layer2.linguistic import version_for
from rag_shield.policy import load_policy

CUE_SETS = {"english_only": {"linguistic": {"multilingual": False}},
            "multilingual": {"linguistic": {"multilingual": True}}}
VISIBLE_LINE = "Skills: Python, SQL"


def _outcome(text: str, policy: dict[str, Any], hidden: bool, tmp: Path) -> dict[str, Any]:
    if hidden:
        path = tmp / "resume.html"
        path.write_text(f"<html><body><p>{VISIBLE_LINE}</p>\n<div style=\"display:none\">"
                        f"{html.escape(text)}</div></body></html>", encoding="utf-8")
        ing = ingest(path)
    else:
        ing = ingest_text(text)
    scr = screen(ing, policy, guard=RuleGuard(policy=policy))
    statuses = {r.status for r in scr.quarantine}
    return {"status": scr.status.value,
            "withheld": bool(statuses & {"quarantined", "review_required"}),
            "quarantined": "quarantined" in statuses}


def _group(cases: list[dict[str, Any]]) -> dict[str, Any]:
    inj = [c for c in cases if c["label"] == "injection"]
    ben = [c for c in cases if c["label"] == "benign"]
    return {
        "detected_withheld": ratio(sum(c["withheld"] for c in inj), len(inj)),
        "detected_quarantined": ratio(sum(c["quarantined"] for c in inj), len(inj)),
        "fpr_withheld": ratio(sum(c["withheld"] for c in ben), len(ben)),
        "fpr_quarantined": ratio(sum(c["quarantined"] for c in ben), len(ben)),
    }


def run_multilingual() -> dict[str, Any]:
    out: dict[str, Any] = {"dataset_version": DATASET_VERSION, "languages": list(LANGUAGES),
                           "cue_sets": {}, "misses": [], "false_positives": []}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, override in CUE_SETS.items():
            policy = load_policy(overrides=override)
            res: dict[str, Any] = {"linguistic_version": version_for(policy)}
            for mode in ("visible", "hidden"):
                cases = []
                for r in rows():
                    cases.append({**r, **_outcome(r["text"], policy, mode == "hidden", tmp)})
                per = {lang: {split: _group([c for c in cases
                                             if c["lang"] == lang and c["split"] == split])
                              for split in ("dev", "test")} for lang in LANGUAGES}
                per["all_test"] = _group([c for c in cases if c["split"] == "test"])
                res[mode] = per
                if name == "multilingual" and mode == "visible":
                    out["misses"] = [c["text"] for c in cases if c["split"] == "test"
                                     and c["label"] == "injection" and not c["withheld"]]
                    out["false_positives"] = [c["text"] for c in cases if c["split"] == "test"
                                              and c["label"] == "benign" and c["withheld"]]
            out["cue_sets"][name] = res
    return out
