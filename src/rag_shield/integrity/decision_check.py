"""Decision-integrity check: decide with vs without suspicious content. Phase 0 stub."""

from __future__ import annotations

from typing import Any

from rag_shield.models import IntegrityResult
from rag_shield.rag.llm import LLMClient


def check(task: str, doc: Any, llm: LLMClient) -> IntegrityResult:
    # Stub never asserts influence either way; delta/threshold are placeholders.
    return IntegrityResult(possible_decision_influence=False, delta=0.0, threshold=20.0)
