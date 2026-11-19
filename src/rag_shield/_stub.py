"""Helpers for Phase 0 stubs. Stubs fail closed: they never report a document as clean."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rag_shield.models import STUB_MARKER, Document, ScanStatus


def stub_document(path: str | Path = "") -> Document:
    return Document(
        doc_id=f"stub:{Path(path).name}" if path else "stub",
        sha256="",
        media_type="unknown",
        ingestion_status=ScanStatus.SCAN_FAILED,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def stub_reason(name: str) -> str:
    return f"{STUB_MARKER}: {name} is a Phase 0 stub"
