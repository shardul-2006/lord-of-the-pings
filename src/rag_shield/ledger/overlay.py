"""Evidence overlay: highlight quarantined spans on the original page. Phase 0 stub."""

from __future__ import annotations

from typing import Any

from rag_shield._stub import stub_reason
from rag_shield.models import Finding


def render_overlay(doc_id: str, page: int, findings: list[Finding]) -> dict[str, Any]:
    # Phase 4 returns a rendered image; the stub returns a labelled placeholder.
    return {"image": None, "reason": stub_reason("render_overlay")}
