"""Layer 1 ingest: canonicalize a document and keep provenance. Phase 0 stub."""

from __future__ import annotations

from pathlib import Path

from rag_shield._stub import stub_document, stub_reason
from rag_shield.models import IngestResult, ScanStatus


def ingest(path: str | Path) -> IngestResult:
    return IngestResult(
        document=stub_document(path),
        status=ScanStatus.SCAN_FAILED,
        reason=stub_reason("ingest"),
    )
