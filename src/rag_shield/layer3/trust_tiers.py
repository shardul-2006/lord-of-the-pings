"""Source trust tiers: per-tier policy overrides (thresholds, spotlighting)."""

from __future__ import annotations

import copy
from typing import Any

from rag_shield.policy import _merge


def tiers(policy: dict[str, Any]) -> list[str]:
    return list(policy.get("tiers", {}))


def apply_tier(policy: dict[str, Any], tier: str | None = None) -> dict[str, Any]:
    """Return a copy of `policy` with the tier's overrides merged in and `tier` recorded."""
    tier = tier or policy.get("default_tier", "external_upload")
    known = policy.get("tiers", {})
    if tier not in known:
        raise ValueError(f"unknown source tier {tier!r}; known: {sorted(known)}")
    out = _merge(copy.deepcopy(policy), known[tier] or {})
    out["tier"] = tier
    return out
