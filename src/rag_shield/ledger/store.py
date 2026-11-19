"""Trust ledger (SQLite in Phase 4). Phase 0 stub."""

from __future__ import annotations

from typing import Any

from rag_shield._stub import stub_reason
from rag_shield.models import Document, Finding, QuarantineRecord


class Ledger:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path

    def add_document(self, document: Document) -> str:
        return stub_reason("Ledger.add_document")

    def add_findings(self, doc_id: str, findings: list[Finding]) -> int:
        return 0

    def list_quarantine(self) -> list[QuarantineRecord]:
        return []

    def release(self, sentence_id: str, reviewer: str) -> dict[str, Any]:
        return {"released": False, "reason": stub_reason("Ledger.release")}
