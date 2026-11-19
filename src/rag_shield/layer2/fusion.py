"""Fuse layout, semantic and linguistic evidence into one score per sentence (Spec E).

    score = w_s*S + w_l*L + w_h*H + w_c*C*max(S, L)       (clipped to [0, 1])

S: guard score if the chunk was escalated, else the calibrated classifier probability.
L: linguistic cue score. H: strongest hiding-signal weight. C: 1 if a carrier signal is present
(carriers only amplify directive evidence, so ordinary metadata stays clean).
Hard rule: a strong hiding signal plus directive syntax is quarantined whatever the score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

QUARANTINED = "quarantined"
REVIEW_REQUIRED = "review_required"
CLEAN = "clean"


@dataclass
class Fused:
    score: float
    disposition: str
    reason: str


def fuse(
    semantic: float,
    linguistic: float,
    hiding: float,
    carrier: bool,
    policy: dict[str, Any],
    hiding_types: list[str] | None = None,
    cues: list[str] | None = None,
) -> Fused:
    w = policy["fusion"]["weights"]
    th = policy["thresholds"]
    content = max(semantic, linguistic)
    score = (
        w["semantic"] * semantic
        + w["linguistic"] * linguistic
        + w["hiding"] * hiding
        + (w["carrier"] * content if carrier else 0.0)
    )
    score = round(min(1.0, max(0.0, score)), 4)

    parts = []
    if hiding_types:
        parts.append(f"hiding({','.join(sorted(hiding_types))})")
    if cues:
        parts.append(f"directive({','.join(cues)})")
    if carrier:
        parts.append("carrier")
    evidence = "+".join(parts) or "none"

    hard_rule = policy["fusion"].get("components", {}).get("hard_rule", True)
    if hard_rule and hiding >= th["strong_hiding"] and linguistic >= th["directive"]:
        return Fused(score, QUARANTINED, f"rule:hiding+directive; {evidence}; score={score}")
    if score >= th["quarantine"]:
        return Fused(score, QUARANTINED, f"score>={th['quarantine']}; {evidence}; score={score}")
    if score >= th["review"]:
        return Fused(score, REVIEW_REQUIRED, f"score>={th['review']}; {evidence}; score={score}")
    return Fused(score, CLEAN, f"low risk; {evidence}; score={score}")
