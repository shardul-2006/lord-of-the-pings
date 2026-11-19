"""Screening policies (YAML). `load_policy()` returns the default policy_v1."""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICY_PATH = Path(__file__).with_name("policy_v1.yaml")


@lru_cache(maxsize=8)
def _load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_policy(
    path: str | Path | None = None, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Load a policy file (default policy_v1) and deep-merge optional overrides."""
    policy = copy.deepcopy(_load(str(path or DEFAULT_POLICY_PATH)))
    return _merge(policy, overrides) if overrides else policy
