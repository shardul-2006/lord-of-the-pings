"""Shield: the library facade (Spec C). Phase 0 stub wiring to the stub modules."""

from __future__ import annotations

from pathlib import Path

from rag_shield.dataset_gate.screen import screen_dataset as _screen_dataset
from rag_shield.layer1.ingest import ingest as _ingest
from rag_shield.layer2 import screen as _screen
from rag_shield.models import DatasetReport, OutputCheck, ScreenedChunk, ScreenResult


class Shield:
    def __init__(self, domain: str = "hr", source_tier: str = "external_upload") -> None:
        self.domain = domain
        self.source_tier = source_tier

    def ingest(self, path: str | Path) -> ScreenResult:
        return _screen(_ingest(path))

    def filter(self, chunks: list[ScreenedChunk]) -> list[ScreenedChunk]:
        # Fail closed: the stub lets nothing through.
        return []

    def validate_output(self, answer: str, chunks: list[ScreenedChunk]) -> OutputCheck:
        return OutputCheck(canary_leak=False, stripped=[], ungrounded=[], clean_answer=answer)

    def screen_dataset(self, path: str | Path, out_dir: str | Path = ".") -> DatasetReport:
        return _screen_dataset(path, out_dir)
