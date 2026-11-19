"""Layer 2: sentence scoring, fusion and reversible quarantine. Phase 0 stub."""

from __future__ import annotations

from typing import Any

from rag_shield._stub import stub_reason
from rag_shield.models import IngestResult, ScanStatus, ScreenResult


def screen(ingest: IngestResult, policy: dict[str, Any] | None = None) -> ScreenResult:
    return ScreenResult(
        document=ingest.document,
        status=ScanStatus.SCAN_FAILED,
        reason=stub_reason("screen"),
    )
