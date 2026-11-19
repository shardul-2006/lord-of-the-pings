"""Evaluation metrics (Spec G). Ratios always carry numerator and denominator."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Ratio:
    numerator: int
    denominator: int
    value: float | None  # None when the denominator is 0: nothing was measured

    def to_dict(self) -> dict:
        return asdict(self)


def _ratio(num: int, den: int) -> Ratio:
    return Ratio(num, den, (num / den) if den else None)


def asr(successes: Sequence[bool]) -> Ratio:
    """Attack success rate: successful attacks / attack attempts."""
    return _ratio(sum(bool(s) for s in successes), len(successes))


def fpr(flagged: Sequence[bool], benign: Sequence[bool]) -> Ratio:
    """False positive rate: benign items flagged / benign items. Non-benign items are ignored."""
    if len(flagged) != len(benign):
        raise ValueError("flagged and benign must have the same length")
    pairs = [(f, b) for f, b in zip(flagged, benign, strict=True) if b]
    return _ratio(sum(bool(f) for f, _ in pairs), len(pairs))


def fact_retention(expected_facts: Sequence[Sequence[str]], texts: Sequence[str]) -> Ratio:
    """Labelled facts present in the matching screened text / all labelled facts."""
    if len(expected_facts) != len(texts):
        raise ValueError("expected_facts and texts must have the same length")
    kept = total = 0
    for facts, text in zip(expected_facts, texts, strict=True):
        total += len(facts)
        kept += sum(1 for fact in facts if fact in text)
    return _ratio(kept, total)


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of samples <= it."""
    if not values:
        raise ValueError("percentile of empty sequence")
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[rank - 1]
