"""Domain adapters: configuration only, same engine.

An adapter names the domain's trusted sources (mapped to trust tiers), the sensitive actions
that should run the decision-integrity check, and policy overrides (thresholds, extra
linguistic cues, integrity task and rubric). `Shield(domain=...)` applies it before the tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_shield.policy import _merge


@dataclass(frozen=True)
class DomainAdapter:
    name: str
    description: str
    trusted_sources: dict[str, str]  # source kind -> trust tier in the policy
    sensitive_actions: tuple[str, ...]  # actions that require the decision-integrity check
    integrity_task: str
    default_question: str
    policy: dict[str, Any] = field(default_factory=dict)  # deep-merged over the base policy

    def tier_for(self, source_kind: str) -> str:
        if source_kind not in self.trusted_sources:
            raise ValueError(f"unknown source kind {source_kind!r} for domain {self.name!r}; "
                             f"known: {sorted(self.trusted_sources)}")
        return self.trusted_sources[source_kind]

    def requires_integrity(self, action: str) -> bool:
        return action in self.sensitive_actions


def _registry() -> dict[str, DomainAdapter]:
    from rag_shield.adapters import hr, paper_review

    return {a.name: a for a in (hr.ADAPTER, paper_review.ADAPTER)}


def domains() -> list[str]:
    return sorted(_registry())


def get_adapter(name: str) -> DomainAdapter:
    reg = _registry()
    if name not in reg:
        raise ValueError(f"unknown domain {name!r}; known: {sorted(reg)}")
    return reg[name]


def apply_domain(policy: dict[str, Any], name: str) -> dict[str, Any]:
    """Return a copy of `policy` with the domain's overrides merged in and `domain` recorded."""
    adapter = get_adapter(name)
    out = _merge(policy, adapter.policy)
    out["domain"] = adapter.name
    out.setdefault("integrity", {})["task"] = adapter.integrity_task
    return out
