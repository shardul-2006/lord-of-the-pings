"""Scanner guard: file-type, size and parse checks before any parsing (Spec F). Phase 0 stub."""

from __future__ import annotations

from pathlib import Path

from rag_shield._stub import stub_reason
from rag_shield.models import GuardResult, ScanStatus


def check_file(path: str | Path) -> GuardResult:
    # Stub fails closed: nothing passes the guard until Phase 2 implements it.
    return GuardResult(status=ScanStatus.SCAN_FAILED.value, reason=stub_reason("check_file"))
