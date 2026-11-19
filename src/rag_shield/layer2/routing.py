"""Cheap-gate routing (Spec E). Every decision is logged, including chunks NOT escalated.

    clearly clean AND no hiding/carrier signal -> pass
    strong hiding or directive signal          -> escalate (even if the classifier says clean)
    otherwise (uncertain, carrier present)     -> escalate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SentenceFeatures:
    sentence_id: str
    text: str
    classifier: float
    linguistic: float
    cues: list[str]
    hiding: float  # max hiding-signal weight, 0 if none
    hiding_types: list[str] = field(default_factory=list)
    carrier_types: list[str] = field(default_factory=list)
    payloads: list[str] = field(default_factory=list)  # e.g. decoded Unicode Tag text


@dataclass
class RoutedChunk:
    chunk_id: str
    sentence_ids: list[str]
    route: str  # "pass" | "escalate"
    reason: str
    log: dict[str, Any]


def _state(f: SentenceFeatures) -> tuple[bool, bool]:
    return (f.hiding > 0, bool(f.carrier_types))


def group_for_routing(features: list[SentenceFeatures], max_chars: int) -> list[list[int]]:
    """Group consecutive sentences into chunks; start a new chunk when the hiding/carrier state
    changes, so suspicious text is never routed together with clean text."""
    groups: list[list[int]] = []
    size = 0
    for i, f in enumerate(features):
        if groups:
            prev = features[groups[-1][-1]]
            if _state(prev) == _state(f) and size + len(f.text) + 1 <= max_chars:
                groups[-1].append(i)
                size += len(f.text) + 1
                continue
        groups.append([i])
        size = len(f.text)
    return groups


def route(
    chunk_id: str, members: list[SentenceFeatures], policy: dict[str, Any]
) -> RoutedChunk:
    th = policy["thresholds"]
    rt = policy["routing"]
    clf_max = max(f.classifier for f in members)
    ling_max = max(f.linguistic for f in members)
    hiding_max = max(f.hiding for f in members)
    hiding_types = sorted({t for f in members for t in f.hiding_types})
    carrier_types = sorted({t for f in members for t in f.carrier_types})

    if hiding_max >= th["strong_hiding"]:
        decision, reason = "escalate", "strong_hiding_signal"
    elif ling_max >= th["directive"]:
        decision, reason = "escalate", "directive_signal"
    elif hiding_max > 0:
        decision, reason = "escalate", "hiding_signal"
    elif carrier_types:
        decision, reason = "escalate", "carrier_signal"
    elif clf_max < rt["clear_clean_classifier"] and ling_max < rt["clear_clean_linguistic"]:
        decision, reason = "pass", "clearly_clean"
    else:
        decision, reason = "escalate", "uncertain"

    log = {
        "chunk_id": chunk_id,
        "sentence_ids": [f.sentence_id for f in members],
        "route": decision,
        "reason": reason,
        "classifier_max": round(clf_max, 4),
        "linguistic_max": round(ling_max, 4),
        "hiding_max": hiding_max,
        "hiding_signals": hiding_types,
        "carrier_signals": carrier_types,
    }
    return RoutedChunk(chunk_id, log["sentence_ids"], decision, reason, log)
